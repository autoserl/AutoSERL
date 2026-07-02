#!/bin/bash
# SpaceMouse 自动绑定脚本

# 等待设备初始化
sleep 1

# 查找 SpaceMouse 的 USB 接口
DEVICE=$(ls /sys/bus/usb/devices/ | grep -E '^[0-9]+-[0-9]+:1.0$' | while read iface; do
    if [ -f "/sys/bus/usb/devices/$iface/../idVendor" ]; then
        vendor=$(cat /sys/bus/usb/devices/$iface/../idVendor)
        product=$(cat /sys/bus/usb/devices/$iface/../idProduct)
        if [ "$vendor" = "256f" ] && [ "$product" = "c63a" ]; then
            # 检查是否已经绑定
            if [ ! -e "/sys/bus/usb/devices/$iface/driver" ]; then
                echo "$iface"
                break
            fi
        fi
    fi
done)

if [ -n "$DEVICE" ]; then
    echo "找到 SpaceMouse 接口: $DEVICE"
    echo "正在绑定到 usbhid 驱动..."
    echo "$DEVICE" > /sys/bus/usb/drivers/usbhid/bind
    echo "绑定成功！"
else
    echo "未找到需要绑定的 SpaceMouse 设备"
fi

