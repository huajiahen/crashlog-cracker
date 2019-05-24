# 如何更好地利用 Crash Log —— 记一次线上 Crash 解决过程的记录

如果你有过几款正式线上 App 的开发经历，你一定也曾被一些奇奇怪怪的 crash 困扰过，他们在你的友盟、Bugly、Crashlystics 上阴魂不散，频率不高但偶有出现，仔细检查崩溃栈却发现他们有的崩在了一些莫名其妙的，你认为不可能会崩溃的位置；有的崩溃栈根本找不到对应的行号在哪里，更别说 debug 了。这时，我们需要一些更给力一点的武器 —— crash log。

通过 crash log，iOS 开发者能获取到的信息其实远超乎大多数人的想象。本文不打算过多地介绍那些众所周知的 crash log 中的内容，在继续读下去之前我默认你已经知道什么是 stack traces，什么是符号化（symbolicate）等术语，也有用过 crash log 解决过诸如数组越界等一些比较浅显的问题。如果你对 LLDB 不够熟悉，是个只知道 `p` 和 `po` 的 LLDB 初级选手，阅读本文前强烈推荐你阅读 objc.io 的[这篇文章](https://objccn.io/issue-19-2/)。除了苹果每隔几年都会少许调整一下获取 crash log 的方式外，其余的 crash log 相关技术基本没有什么变化。

## 从哪里获取 Crash Log

巧妇难为无米之炊，我们想要用 crash log 解决问题，首先得拿到 crash log。

#### 模拟器

一般来说没有特别大的必要获取模拟器的日志，因为绝大多数使用模拟器的情况都是从 Xcode 里直接 run 的，崩溃现场都有要啥 crash log 呢😂。然后天有不测风云，如果哪天真的你直接从模拟器打开 App，而且出现了 crash，日志还是找得回来的。用 Finder 打开 `~/Library/Logs/DiagnosticReports` 你能看到以 `进程名+日期+时间戳+设备名命.crash` 命名的文件，这些就是 crash 日志了。需要注意的是，crash 日志路径和系统还有 Xcode 版本有关，本文的所有操作的环境均为 macOS 10.14 + Xcode 10.1。

#### 测试用机

如果能直接拿到需要 crash log 的设备，把它连到你的电脑上，在 Xcode 的 Window -> Devices and Simulators 里的 Device 面板，在左侧选中你的设备，点击右侧 `View Device Logs` 就会列出这个设备上的所有 log 了，其中 type 为 crash 的就是我们关注的 crash log。

#### 已经发布到 AppStore 的 app

但除了内部测试，大多数情况我们并不能拿到发生 crash 的设备。苹果为 TestFlight 和 App Store 上的 app 提供了 crash log 收集功能。该功能只有在用户每次更新或激活 iOS / macOS 系统后主动选择同意 Apple 分享 App 使用数据和 crash 信息给开发者的选项后才能工作。

此外，为了获得访问日志的权限，你需要在 App Store Connect 上拥有对应 App 的 developer 权限后，在你的 Xcode 的 Preferences -> Accounts 里登录你的账号，到 Window -> Organizer 窗口里选择 Crashes 面板，最左侧一栏就会列出所有你有权限访问的 App，第二栏会分 App 版本列出苹果收集到的你的用户发生的 crash 内容。但我们要的不仅是这些，我们需要 `.crash` 文件来继续后面的操作。右击你关注的某个 crash，选择 `Show in Finder`，会定位到一个位置为 `~/Library/Developer/Xcode/Products/${你 app的bundleID}/${版本号 (build号)}/Crashes/AppStore/${一串乱码编号}.xccrashpoint` 文件夹。右击被选中的那个 `.xccrashpoint` 文件，选择 `Show Package Contents`，再依次进入 `DistributionInfos` -> `all` -> `Logs`，里面会有一个到数个的 `.crash` 文件，苹果是按崩溃栈和崩溃类型归类 crash 的，通常来说这些 crash log 都是同一个 bug 导致的 crash，但有时同一个 bug 会有多种不同的表现。

#### 还有其他路子吗

除了苹果的服务外，还有一些第三方提供了这些服务，国外的有 Crashlytics，国内常用的有友盟、腾讯的 bugly 等。相对苹果的服务，他们通常会有提供一些更漂亮的统计功能，以及将用户 ID 与 crash 关联等功能，但由于程序的运行机制限制，他们能拿到的信息必然要比系统少，一般只有堆栈信息和设备型号、系统版本等，本文所说的 crash log 指的都是 iOS 系统生成的日志，不包括这些第三方日志。

## Crash Log 里有啥

就在不久前我们也遇到了开头所说的硬骨头 bug，本地极难复现，崩溃信息又莫名其妙。庆幸的是 App Store 有为我们成功捕获到几个崩溃日志，让我们修复这个 bug 变为可能。我们拿出这次 crash log 作为例子给大家分享一下，如何更好地利用 crash log。由于文件很长，我们一段一段地看。

### 运行环境

```
Incident Identifier: 92863615-57CE-45C1-84CD-E030A7A6C429
CrashReporter Key:   affee827f837b5a5be6f46df116d48cafd2fe552
Hardware Model:      iPhone9,2
Process:             Telis [397]
Path:                /private/var/containers/Bundle/Application/04136047-A194-40B1-B7A3-FA650D30BB66/Telis.app/Telis
Identifier:          com.liulishuo.Telis
Version:             4316 (2.7.0)
Code Type:           ARM-64 (Native)
Role:                Foreground
Parent Process:      launchd [1]
Coalition:           com.liulishuo.Telis [495]


Date/Time:           2018-07-11 10:34:40.3214 +0800
Launch Time:         2018-07-11 09:34:56.2155 +0800
OS Version:          iPhone OS 11.4 (15F79)
Baseband Version:    3.70.00
Report Version:      104
```
这段没什么特别需要说明的信息，从 Crashlytics 的统计信息中我们已经知道这个 crash 和设备型号，系统版本都没有什么关联。

### 错误信息

```
Exception Type:  EXC_BAD_ACCESS (SIGSEGV)
Exception Subtype: KERN_INVALID_ADDRESS at 0x00000005bee2bec8
VM Region Info: 0x5bee2bec8 is not in any region.  Bytes after previous region: 16624303817  
      REGION TYPE                      START - END             [ VSIZE] PRT/MAX SHRMOD  REGION DETAIL
      MALLOC_NANO (reserved) 00000001d8000000-00000001e0000000 [128.0M] rw-/rwx SM=NUL  ...(unallocated)
--->  
      UNUSED SPACE AT END

Termination Signal: Segmentation fault: 11
Termination Reason: Namespace SIGNAL, Code 0xb
Terminating Process: exc handler [0]
Triggered by Thread:  0
```

这段我们得知崩溃的原因是出现 `EXC_BAD_ACCESS` 异常，子类型是 `KERN_INVALID_ADDRESS`，通常是访问到非法地址导致的，访问的地址则是 `0x5bee2bec8`。接下来提供了一段更详细的信息，告诉我们访问的地址不属于虚拟内存（VM）的任何 region，并给出了访问地址在虚拟内存中位置和周围的 region 布局。这里简单介绍一下 region，region 是在 page 再下一级的内存分配单元，通过让不同大小的对象在不同 region 上分配空间，以减少内存碎片，并使用更适合的分配策略。在最后 `Triggered by Thread:  0` 告诉我们导致崩溃的线程是主线程。

回到我们的 crash log 上，有时这一段后面还会跟上一些更具体的描述信息：

```
Application Specific Information:
Fatal error: Unexpectedly found nil while unwrapping an Optional value
```

这种明确告诉我们是什么原因崩溃的是最喜闻乐见的了，譬如上面这段，很明显是 Swift 的 optional 类型被强制解包。这种 bug 通常都比较好修复，实在不懂可以把这段文本贴到 Stack Overflow 上搜一下。然而可惜的是，本次要讨论的 crash 并没有这些内容。

继续往下看，就是大家通常最关心的部分了，术语叫 stack traces 或 backtraces，可以翻译成堆栈回溯，通常我们也会叫它崩溃堆栈（crash stack）。前面已经知道崩溃发生在主线程，这里先省略其他线程的内容。

### 堆栈回溯

```
Thread 0 name:
Thread 0 Crashed:
0   libobjc.A.dylib               	0x00000001805b17f4 objc_object::release() + 16 (objc-object.h:531)
1   SingleQuestionTestModule      	0x0000000102692f7c TelisFlowQuestionStreamer.reset() + 416 (TelisFlowQuestionStreamer.swift:0)
2   SingleQuestionTestModule      	0x0000000102696310 specialized TelisFlowQuestionStreamer.socketClosed(reason:code:wasClean:error:) + 308 (TelisFlowQuestionStreamer.swift:224)
3   SingleQuestionTestModule      	0x0000000102698e50 partial apply for closure #4 in TelisFlowQuestionStreamer.buildSocket() + 92 (TelisFlowQuestionStreamer.swift:0)
4   TPNetworking                  	0x0000000102fda9ac closure #6 in InnerWebSocket.step() + 228 (WebSocket.swift:783)
5   TPNetworking                  	0x0000000102fec784 partial apply for closure #1 in InnerWebSocket.fire(_:) + 20 (WebSocket.swift:936)
6   TPNetworking                  	0x0000000103025ad8 thunk for @callee_guaranteed () -> () + 36 (HTTPServiceSessionDelegate.swift:0)
7   libdispatch.dylib             	0x0000000180ccca60 _dispatch_client_callout + 16 (object.m:507)
...
```

通常拿到崩溃堆栈信息，我们最关心的无非是两块：实际发生崩溃的 frame（栈帧） 0 的代码，和调用方法在我们自己的 binary 内的 frame。在这里，frame 0 是 libobjc 的 `objc_object::release()` 方法，说明是内存管理出问题了，很有可能是对象被 overrelease。可能有些人会问，为什么 ARC 也会有内存管理问题？这个问题我们先留着不答，到后面我们自然会明白。继续往下看，这段代码中涉及到我们自己代码的 frame 号最小的一行是 frame 1，这里告诉我们是 SingleQuestionTestModule 模块的 `TelisFlowQuestionStreamer.reset()` 方法里触发了崩溃。后面紧接着的是此时执行到的行号，TelisFlowQuestionStreamer.swift 的 0 行。

### 碰到困难了……以及我们的秘密武器

这可真是大事不妙，我们最不想见到的事情发生了：行号信息丢失。在进行代码优化的编译配置下，行号信息丢失是时不时会出现的，有时我们可以从调用栈的前后帧推断出实际出现问题的是哪一行，但像这个例子里，下一帧调用的是系统的 release 方法，在 ARC 中我们很难判断哪些位置会被编译器自动插入 release，更何况有那么多的 retain/release，也不知道是哪个呀。

这时候需要拿出我们的秘密武器，很多人熟悉又陌生的 lldb。lldb 是 llvm 的编译工具链中的 debug 工具，平时使用 Xcode 时打断点、检查运行中的变量值等操作其实都是 Xcode 将 lldb 的运行结果进行了可视化的结果。除了 lldb 外，我们还需要准备好的是当时提交 App Store 的 archive 文件，在 Xcode 的 Organizer 里的 Archives 面板里能找到导出功能。然后我们需要做的是打开 Terminal，输入 lldb。没看错，我们天天接触的 lldb 其实是个可以脱离 Xcode 独立使用的命令行工具。

```shell
$ lldb
(lldb)
```

接着调用 `command script import lldb.macosx.crashlog` 命令，你能看到类似下文的输出。

```
(lldb) command script import lldb.macosx.crashlog
"crashlog" and "save_crashlog" command installed, use the "--help" option for detailed help
"malloc_info", "ptr_refs", "cstr_refs", and "objc_refs" commands have been installed, use the "--help" options on these commands for detailed help.
```

> #### troubleshooting
> 在使用 LLDB `command script import lldb.macosx.crashlog` 的时候你有可能碰到 import 标准库出错的问题，这是因为你安装了非 macOS 自带 python 从而导致 python 标准库搜索路径会指向你安装的 python 版本，而 lldb 会无视你的搜索路径设置，强制使用系统自带 python 来 import 所需要的标准库， 最终导致的 import 不兼容版本的标准库。我暂时没有找到太好的解决方案，建议你如果碰到这个问题，可以临时修改 python 的搜索路径使其指向系统内建 python `/usr/bin/python`；如果是用 brew 安装的 python，可以执行 `brew unlink python2` 临时解除 python 的符号链接。

lldb 是支持通过 python 脚本调用的，在脚本中我们只需要 `import lldb` 即可，本文不详细介绍 python 中 lldb 库的使用，感兴趣的可以参考 [lldb Python API文档](https://lldb.llvm.org/python_reference/index.html)。刚刚通过 `command script import` 引入的 便是一段  Xcode 自带的 python 脚本，位于 `/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python` 下。该目录下，还有一些其他的 lldb 脚本，本文也不多做介绍，不过此外如果你有自己的脚本也可以通过 `command script import` 命令引入。如果你希望某个脚本每次 lldb 启动都自动加载，可以在`~/.lldbinit`文件中加入下面的内容（如果文件不存在就自己新建一个，你懂的）：

```
# ~/.lldbinit
...
command script import path/to/your/script.py
```

说回到 `lldb.macosx.crashlog` ，这个脚本的主要功能是解析 Darwin 内核的 crash log，通过 crash log 中的信息还原尽可能地还原事故现场。是不是特别神奇，小小 crash log 竟然有如此能量。使用方法很简单，crashlog 命令加上我们需要解析的 crash log 文件路径即可。

```
(lldb) crashlog path/to/crashlog.crash
```

如果你心急地按前面步骤操作的话，这里肯定已经看到满屏幕的报错了。这是由于这个脚本的一些局限性导致的。知其然更要知其所以然，解决这个问题需要我们真正理解这个脚本是怎么工作的。但在我们揭开这个脚本的神秘面纱前，我们还需要 crash log 中的一些额外信息。

### 寄存器信息和 Binary Image

我们先把关注点回到 crash log 上。紧跟在崩溃堆栈下面的内容是崩溃发生时崩溃线程的寄存器信息，平时联机调试崩溃的时候我们可以随意地切换到不同线程的不同栈帧上查看当前的寄存器内容以及所有内存中变量的内容，但在用户发生 crash 的时候，把整个虚拟内存中的内容全部导出给开发者 debug 显然是不切实际的，我们没办法要求用户传一个几百兆的日志给我们，更何况内存中或许有大量敏感信息。

```
Thread 0 crashed with ARM Thread State (64-bit):
    x0: 0x00000001c0a290c0   x1: 0x00000001c0a290c0   x2: 0x0000000000000008   x3: 0x0000000180ea906c
...
   x28: 0x00000001026c64ea   fp: 0x000000016da86810   lr: 0x0000000102692f7c
    sp: 0x000000016da86810   pc: 0x00000001805b17f4 cpsr: 0x20000000

```

尽管系统只为我们留了寄存器中这么一点信息，但如果使用得当，我们还是能通过它获得一些额外的帮助。譬如当问题出在 crash 线程的顶部栈帧，若 crash 位置前后有 br/blr 指令，可以通过算出要移动到的地址进而帮助你解决 crash。不过这里我们不需要寄存器里的信息，继续往下看到 Binary Image。

```
Binary Images:
0x102378000 - 0x10245ffff YourApp arm64  <98a3f237f7b1345b93cb685fbbab7c08> /var/containers/Bundle/Application/B8D077AF-2EC6-47F9-9367-C8DD91E14BA2/Telis.app/Telis
0x1024c4000 - 0x1024f3fff IGListKit arm64  <413e42f511d833f6972b4a5ed9c05573> /var/containers/Bundle/Application/B8D077AF-2EC6-47F9-9367-C8DD91E14BA2/Telis.app/Frameworks/IGListKit.framework/IGListKit
...
0x180d6d000 - 0x180deafff libsystem_c.dylib arm64  <4fdfb9bed517340693481047718c8b0b> /usr/lib/system/libsystem_c.dylib
...
```

Binary Image 字段列出了 app 已经链接的所有动态链接库信息，不仅包括 app 的主可执行文件（`YourApp`），我们自己的 Framework（`IGListKit`），还有系统的动态链接库（`libsystem_c.dylib`）

以第一条 app 主可执行文件的记录为例，`0x102378000 - 0x10245ffff` 是其在内存中的地址范围，接下来以此是其名字，指令集类型、uuid、存储位置。出于安全原因，对于支持 PIE（Position Independent Execution）的 App iOS 每次加载过程都会进行内存随机化，因此即使在同一个设备上同一个 binary image 在不同 crash log 里地址也是不同的。此外 UUID 是编译时决定的，即使是同一份代码在同一台设备上每次编译也是不一致的，这也是为什么 dSYM 文件不能混用，且我们在上面说到准备工作的要求一定要是提交 App Store 时的 archive。另一个涉及到随机化的点是最后一条安装位置，iOS App 在安装时不像 macOS 一样直接安装在 Application 目录，而是会被指定在 Application 目录的一个 UUID 构成的目录下，这就是前面我们运行 crash log 命令会报错的原因。

所以说到底那个脚本做的事情很容易理解：读取每一段 Binary Image 的信息，在其描述的路径找到对应的二进制文件，将其中对应指令集的 `_TEXT` 段加载到正确的内存位置，然后使用 dSYM 文件将所有 symbols 符号化以便于阅读。

但这里有几个问题。

首先这个脚本最初的设计的目的是调试本机的 crash log，而如果我们的 crash log 是来自于真实设备而不是模拟器，那我们电脑上相同的路径下必然找不到对应的二进制文件，之后的操作完全没法继续。这个问题需要分两种情况分别处理：我们打包进去的和 iOS 系统提供的。
我们自己的 Binary Image 可以通过修改 crash log 中对应记录的磁盘位置让脚本找到我们本地 archive 文件里的二进制文件，具体来说就是把文件中诸如 `/var/containers/Bundle/Application/B8D077AF-2EC6-47F9-9367-C8DD91E14BA2/YourAppName.app` 这样的路径全部替换成 `path/to/YourAppName.xcarchive/Products/Applications/YourAppName.app`。此外因为 Swift 直到 4.2 都未实现 ABI 稳定，所以不能通过系统内置一个 Swift 来统一为所有 Swift 提供运行时支持，因此如果你的项目使用了 Swift 开发，还会包括 Swift 的 runtime / 标准库 / 用于辅助 iOS SDK 标准库桥接到 Swift 的动态链接库等。对于系统自带的动态链接库会比较麻烦，你需要一个和 crash log 中描述的系统版本完全一致的设备，将其链接到你的电脑，让 Xcode 完成 copy debug info 的操作，再将那些动态链接库指向 `~/Library/Developer/Xcode/iOS DeviceSupport/` 目录中的版本。

其次是 crashlog 这个脚本自身有些问题，脚本不是通过指定 dSYM 文件路径，而是会使用另一个脚本利用 macOS 的 spotlight 功能寻找 dSYM 文件。然而不知道苹果开源这些 lldb 工具集的时候是怎么考虑的，这个辅助脚本很神奇地没有被开源。

第三个问题是 Bitcode 引起的。如果你不了解 Bitcode 技术，这里简单解释一下。苹果在 WWDC 2015 开始在 App Store 开始提供 Bitcode 功能，开发者提交到 App Store 的二进制文件不只是用户设备上真正运行的机器码，会额外附带一份中间码，也就是 Bitcode。Bitcode 是 clang / swiftc -> llvm 编译体系下的中间产物，可以进一步编译成机器码。按苹果的说法，当编译器有优化或者有新的指令集架构时，他们会使用 Bitcode 生成新的机器码代替你的。但非常尴尬的是，因为 Bitcode 生成是在 swiftc 编译之后的流程，swift 社区每天都有大量对编译器优化，而这些优化是不能通过使用 Bitcode 技术享受到的；其次 Bitcode 可能导致你的代码和你本地编译的版本不一致，而你只能从 App Store Connect 下载到 dSYM 文件而没有二进制文件。在我们的例子下就完全不能进行后续的 crash log 分析工作了。

> 题外话：绝大多数情况 Bitcode 编译的版本和你直接使用最新版本 Xcode 编译的基本是一致的。虽然不清楚苹果主动对你的代码重新从 Bitcode 生成机器码的时机，但毕竟尽管理论上可行，实际上苹果不太可能频繁地重新生成你的程序的机器码。通过一些简单的 hack 操作强行使用本地编译的版本解析开启 Bitcode 后的用户 crash log 通常是能够被 lldb 正确解析的。

这里我提供了一个修改版本的 crash log 脚本，能通过指定 archive 文件位置来帮你解决前面提到的这些问题，加载 dSYM 时会优先搜索 archive 文件内的版本，且使用名字匹配而非 uuid 匹配，以可能会匹配错误为代价换取尽可能高的脚本兼容性。你可以在 https://github.com/huajiahen/crashlog-cracker 找到，用法在项目 README 中有介绍，这里不再赘述。

```
$ python CrashlogCracker.py --archive Telis.xcarchive/ crashlog.crash
crashlog rebuild at converted.crashlog.crash
```

使用这个脚本“破解” crashlog 后，我们回到 lldb 重新还原一下事故现场：

```
(lldb) crashlog path/to/converted.crashlog.crash
```

如果你提供的 Archive 没有问题（与 crash log 里写明的 App 版本一致，且没有文件丢失或损坏），接下来能看到数条 `Getting symbols for 9951067F-2686-3CC0-936C-43B682E0A0CD /xxx/YourFramework.framework/YourFramework... ok` 的消息，紧接着就是修复成功的 crash log 了！

```
Thread[0] EXC_BAD_ACCESS (SIGSEGV) (KERN_INVALID_ADDRESS at 0x00000005cb31bec8)
[  0] 0x00000001805b17f4 libobjc.A.dylib`objc_object::release() + 16

     0x00000001805b17e4:      stp x29, x30, [sp, #-0x10]!
     0x00000001805b17e8:      mov x29, sp
     0x00000001805b17ec:      ldr x8, [x0]
     0x00000001805b17f0:      and x8, x8, #0xffffffff8
 ->  0x00000001805b17f4:     ldrb w8, [x8, #0x20]
     0x00000001805b17f8:      tbz w8, #0x1, 0x1800cd854
     0x00000001805b17fc:     tbnz x0, #0x3f, 0x1800cd834
     0x00000001805b1800:      orr x8, xzr, #0x200000000000
     0x00000001805b1804:     ldxr x9, [x0]

[  1] 0x0000000102692f7b SingleQuestionTestModule`SingleQuestionTestModule.TelisFlowQuestionStreamer.(reset in _18DE03F5A23DB8E8946B005331DA88B6)() -> () [inlined] SingleQuestionTestModule.TelisFlowQuestionStreamer.(socket in _18DE03F5A23DB8E8946B005331DA88B6).setter : Swift.Optional<TPNetworking.WebSocket> + 11 at TelisFlowQuestionStreamer.swift:0
[  1] 0x0000000102692f70 SingleQuestionTestModule`SingleQuestionTestModule.TelisFlowQuestionStreamer.(reset in _18DE03F5A23DB8E8946B005331DA88B6)() -> () + 404 at TelisFlowQuestionStreamer.swift:81
...
```

瞧瞧 lldb 帮我们找到了什么！首先它帮我们直接找到了 crash 所在行的汇编指令，其次还帮我们准确定位到了 frame 1 实际上是由 `TelisFlowQuestionStreamer.swift:81` 这行 inline 调用了 socket 属性的 setter，由于某种编译器问题导致一些 inline 方法行号丢失了。

按一般的理解，当使用譬如 Codable 协议等会触发编译器自动生成代码的技术，显然会产生 debug 信息为 0 行的情况，因为这些指令本就没有对应的实际代码；不过在 inline 调用时插入代码也会有行号不正常的情况，这个行为可能有点反直觉。实际上解释起来也很简单，因为 inline 方法调用实质上是编译器把被调用方法的方法体复制到每一个调用处替换原始代码，而复制过去的代码很难说是属于被替换行还是原始所属行；另一方面每一个栈帧所处的行号和文件只能是一个，不能同时属于多个文件或行号。当没有足够的信息来将一个栈帧中的 inline 调用拆解出来是，你就会得到这样莫名其妙的崩溃信息。对于大多数语言，你可以自己标记 inline 方法，而你没有标记 inline 的方法，在开启编译器优化时也会经常碰到自动内联优化，典型的就是文中碰到的 setter 方法 inline，此外有些语言会有尾递归优化导致的调用栈信息丢失，而这些通常是你在 debug 程序时不会碰到的情况。通过本文的介绍，再碰到这类问题时，你就可以通过熟悉又陌生的老朋友 lldb 来帮助你解决问题。

为什么 setter 内部会发生 `objc_object::release() + 16` 的 crash 呢？实际上 `objc_object::release() + 16` 处发生 EXC_BAD_ACCESS 的 crash 是一种比较常见的问题，如果你是有经验的开发者，尤其是对 Objective-C 的对象结构及的内存分配策略有了解，你会很快意识到这里发生了 over-release。ObjC 对象会在对象头部存储指向该对象所属的类的 isa 指针，在调用 release 方法时会访问到这一字段。然而，在对象被释放（dealloc）时，对象占用内存会被释放，头部指针会被修改指向一块未被分配到内存区域。当尝试访问这个指针时，系统发现这块区域内存还未分配，属于非法区域，自然会抛出 EXC_BAD_ACCESS 的错误了。

> 为什么会出现 over-release 的情况超出了本文的范围。如果你想了解更多，可以访问[苹果的开源网站](https://opensource.apple.com)，Objective-C 的对象结构源码在 objc4 项目中能找到，而关于内存分配管理则在 libmalloc 项目中。

### 扩展阅读
文中介绍的 crashlog 使用技巧，主要参考了 [WWDC18-Session 414 Understanding Crashes and Crash Logs](https://developer.apple.com/videos/play/wwdc2018/414/) 以及 Apple 关于 crash log 的 technical note [Technical Note TN2151: Understanding and Analyzing Application Crash Reports](https://developer.apple.com/library/archive/technotes/tn2151/_index.html)。你可以观看 session 视频了解更多的关于 crash log 的知识。
