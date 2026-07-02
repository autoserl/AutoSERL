import pyspacemouse
import time

print("正在打开 SpaceMouse...")
success = pyspacemouse.open()

if success:
    print("✓ SpaceMouse 已成功连接！")
    print("\n请移动或旋转 SpaceMouse，按任意按钮测试...")
    print("按 Ctrl+C 退出\n")
    
    try:
        last_buttons_raw = None
        last_buttons_list = None

        def buttons_to_list(b):
            """将不同格式的 buttons 字段统一解析为布尔列表。

            支持的输入类型：None, int, bytes/bytearray, list/tuple, 以及可迭代对象。
            返回值：按位布尔列表，最低位为按钮0。
            """
            if b is None:
                return []
            if isinstance(b, int):
                bits = max(b.bit_length(), 8)
                return [bool((b >> i) & 1) for i in range(bits)]
            if isinstance(b, (bytes, bytearray)):
                out = []
                for byte in b:
                    for i in range(8):
                        out.append(bool((byte >> i) & 1))
                return out
            if isinstance(b, (list, tuple)):
                return [bool(x) for x in b]
            # 其他可迭代类型
            try:
                return [bool(x) for x in b]
            except Exception:
                return [str(b)]

        VERBOSE = False  # 若想保留原始调试信息请设为 True
        DEBOUNCE_SECONDS = 0.05  # 去抖阈值，忽略 50ms 内的抖动
        last_change_times = {}

        # 可选的按钮名字映射，按需修改
        BUTTON_NAMES = {
            0: 'Button_0',
            1: 'Button_1',
        }

        def button_name(i):
            return BUTTON_NAMES.get(i, f'Button_{i}')

        while True:
            state = pyspacemouse.read()
            
            if not state:
                time.sleep(0.01)
                continue

            moved = any(abs(val) > 0.01 for val in [state.x, state.y, state.z, state.roll, state.pitch, state.yaw])
            buttons_raw = getattr(state, "buttons", None)
            buttons_list = buttons_to_list(buttons_raw)
            buttons_changed = (last_buttons_raw is None) or (buttons_list != last_buttons_list)

            # 当有运动或按钮状态变化时打印（包含友好的按键事件输出）
            if moved or buttons_changed:
                if moved:
                    print(f"位置: X={state.x:6.2f} Y={state.y:6.2f} Z={state.z:6.2f}  "
                          f"旋转: Roll={state.roll:6.2f} Pitch={state.pitch:6.2f} Yaw={state.yaw:6.2f}")

                now = time.time()

                # 找出发生变化的按键并报告按下/释放，带去抖
                if last_buttons_list is not None:
                    maxlen = max(len(last_buttons_list), len(buttons_list))
                    for i in range(maxlen):
                        prev = last_buttons_list[i] if i < len(last_buttons_list) else False
                        cur = buttons_list[i] if i < len(buttons_list) else False
                        if prev != cur:
                            # 去抖：若上次该键变化时间过短则忽略
                            last_time = last_change_times.get(i, 0)
                            if now - last_time < DEBOUNCE_SECONDS:
                                if VERBOSE:
                                    print(f"[VERBOSE] 忽略抖动: {button_name(i)} {int(prev)}->{int(cur)} (间隔 {now-last_time:.3f}s)")
                                continue
                            last_change_times[i] = now
                            action = '按下' if cur else '释放'
                            print(f"{button_name(i)} {action}")
                else:
                    # 首次读取，简单列出状态（可选）
                    if buttons_list:
                        print("初始按钮状态:", [int(x) for x in buttons_list])

                if VERBOSE or last_buttons_raw is None or buttons_changed:
                    # 保留可选调试输出（原始 repr 与解析后列表）
                    if VERBOSE:
                        print("[DEBUG] raw buttons repr:", repr(buttons_raw), " type:", type(buttons_raw).__name__)
                        print("[DEBUG] parsed buttons list:", buttons_list)

                last_buttons_raw = buttons_raw
                last_buttons_list = buttons_list
            
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\n程序已退出")
else:
    print("✗ 无法打开 SpaceMouse")