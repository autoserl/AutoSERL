# SpaceMouse 配置说明

## 问题描述

SpaceMouse Wireless BT 在 Linux 系统上可能遇到以下问题：
1. pyspacemouse 无法检测到设备："No found any connected or supported devices"
2. USB 设备虽然被系统识别，但没有绑定到 HID 驱动

## 解决方案

### 1. 安装依赖
```bash
pip install cffi pyspacemouse
```

### 2. 创建 udev 规则

创建文件 `/etc/udev/rules.d/99-spacemouse.rules`（需要 sudo 权限）：

```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="256f", ATTRS{idProduct}=="c63a", MODE="0666"
SUBSYSTEM=="input", ATTRS{idVendor}=="256f", ATTRS{idProduct}=="c63a", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="256f", ATTRS{idProduct}=="c63a", MODE="0666"' | sudo tee /etc/udev/rules.d/99-spacemouse.rules
```

### 3. 重新加载 udev 规则

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 4. 配置自动绑定（已完成！）

udev 规则已经配置为在设备连接时自动绑定驱动。下次插入 SpaceMouse 时会自动工作。

如果自动绑定失败，可以使用快捷命令手动绑定：

```bash
bind-spacemouse
```

或者直接运行绑定脚本：
```bash
sudo /home/cxl/liyu/serl/spacemouse/bind_spacemouse.sh
```

**命令说明：**
`echo "1-4:1.0" | sudo tee /sys/bus/usb/drivers/usbhid/bind` 这个命令的作用是：
- 将 USB 设备接口 `1-4:1.0` 手动绑定到 `usbhid` 驱动程序
- `1-4:1.0` 是设备的 USB 地址（1=总线号，4=端口号，1.0=接口号）
- 通过写入 `/sys/bus/usb/drivers/usbhid/bind` 文件告诉内核加载驱动

<!-- 为什么需要这样做？
在您的情况下，SpaceMouse 设备虽然被 Linux 系统识别（通过 lsusb 可以看到），但是没有自动加载 HID 驱动程序，所以 pyspacemouse 无法访问它。
通过向 bind 文件写入设备接口标识符，我们告诉内核：
> "请将这个设备接口绑定到 usbhid 驱动程序" -->


<!-- 绑定后的效果：
内核加载 usbhid 驱动程序
创建 /dev/hidraw3 设备节点
pyspacemouse 可以通过这个设备节点访问 SpaceMouse -->

### 5. 验证设备

检查 hidraw 设备是否创建：
```bash
ls -la /dev/hidraw*
```

应该看到一个新的 `/dev/hidraw*` 设备，权限为 `crw-rw-rw-`（0666）。

## 测试

运行测试脚本：
```bash
python test.py
```

成功输出应该显示：
- "SpaceMouse Wireless [NEW] found"
- 位置和旋转数据实时更新

## 设备信息

- **厂商**: 3Dconnexion
- **产品**: SpaceMouse Wireless BT
- **USB ID**: 256f:c63a
- **接口类型**: HID (Human Interface Device)

## 故障排除

### 问题：找不到设备
1. 确认 USB 连接：`lsusb | grep 3Dconnexion`
2. 检查驱动绑定：`readlink /sys/bus/usb/devices/1-X:1.0/driver`
3. 查看内核日志：`sudo dmesg | grep -i spacemouse`

### 问题：权限被拒绝
1. 检查 hidraw 设备权限：`ls -la /dev/hidraw*`
2. 确认 udev 规则生效：`udevadm info -a -n /dev/hidrawX | grep -i 256f`

### 问题：设备断开后重新连接失败
运行快捷命令：`bind-spacemouse`

### 快捷命令
已添加到 `~/.bashrc` 的别名：
- `bind-spacemouse`: 快速绑定 SpaceMouse 驱动

