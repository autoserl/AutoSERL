import pyspacemouse
import time

print("正在打开 SpaceMouse...")
success = pyspacemouse.open()

if success:
    print("✓ SpaceMouse 已成功连接！")
    print("\n请移动或旋转 SpaceMouse，按任意按钮测试...")
    print("按 Ctrl+C 退出\n")
    
    try:
        last_buttons = None
        while True:
            state = pyspacemouse.read()
            
            if not state:
                time.sleep(0.01)
                continue

            moved = any(abs(val) > 0.01 for val in [state.x, state.y, state.z, state.roll, state.pitch, state.yaw])
            buttons_changed = (last_buttons is None) or (state.buttons != last_buttons)

            # 当有运动或按钮状态变化时打印
            if moved or buttons_changed:
                if moved:
                    print(f"位置: X={state.x:6.2f} Y={state.y:6.2f} Z={state.z:6.2f}  "
                          f"旋转: Roll={state.roll:6.2f} Pitch={state.pitch:6.2f} Yaw={state.yaw:6.2f}", end='  ')
                # 总是显示按钮当前状态（只在变化或首次读取时打印）
                print(f"按钮: {state.buttons}")
                last_buttons = state.buttons
            
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\n程序已退出")
else:
    print("✗ 无法打开 SpaceMouse")