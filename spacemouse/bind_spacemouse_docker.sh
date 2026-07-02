#!/bin/bash
# SpaceMouse Docker 容器内绑定脚本

echo "=== SpaceMouse Docker 绑定脚本 ==="

# 检查是否在容器内
if [ -f /.dockerenv ]; then
    echo "✓ 检测到 Docker 环境"
else
    echo "⚠ 警告：似乎不在 Docker 容器内"
fi

# 检查是否有足够权限
if [ ! -w /sys/bus/usb/drivers/usbhid/bind ]; then
    echo "✗ 错误：没有写入权限"
    echo "  请确保容器以 --privileged 模式运行"
    echo "  或挂载了 -v /sys:/sys"
    exit 1
fi

# 等待设备初始化
sleep 1

echo "正在搜索 SpaceMouse 设备..."

# 查找 SpaceMouse 的 USB 接口
DEVICE=$(ls /sys/bus/usb/devices/ 2>/dev/null | grep -E '^[0-9]+-[0-9]+:1.0$' | while read iface; do
    if [ -f "/sys/bus/usb/devices/$iface/../idVendor" ]; then
        vendor=$(cat /sys/bus/usb/devices/$iface/../idVendor 2>/dev/null)
        product=$(cat /sys/bus/usb/devices/$iface/../idProduct 2>/dev/null)
        if [ "$vendor" = "256f" ] && [ "$product" = "c63a" ]; then
            # 检查是否已经绑定
            if [ ! -e "/sys/bus/usb/devices/$iface/driver" ]; then
                echo "$iface"
                break
            else
                echo "设备 $iface 已经绑定到驱动" >&2
            fi
        fi
    fi
done)

echo $DEVICE

if [ -n "$DEVICE" ]; then
    echo "✓ 找到 SpaceMouse 接口: $DEVICE"
    echo "正在绑定到 usbhid 驱动..."
    
    if echo "$DEVICE" > /sys/bus/usb/drivers/usbhid/bind 2>/dev/null; then
        echo "✓ 绑定成功！"
        
        # 等待设备节点创建
        sleep 1
        
        # 显示创建的设备
        echo ""
        echo "可用的 hidraw 设备："
        ls -la /dev/hidraw* 2>/dev/null || echo "  未找到 hidraw 设备"
        
        # 检查权限
        echo ""
        echo "设备权限检查："
        for dev in /dev/hidraw*; do
            if [ -e "$dev" ]; then
                perms=$(stat -c "%a" "$dev")
                if [ "$perms" = "666" ]; then
                    echo "  ✓ $dev: 可读写 ($perms)"
                else
                    echo "  ⚠ $dev: 权限不足 ($perms)，可能需要 root 或修改权限"
                fi
            fi
        done
        
        exit 0
    else
        echo "✗ 绑定失败！"
        exit 1
    fi
else
    echo "✗ 未找到需要绑定的 SpaceMouse 设备"
    echo ""
    echo "调试信息："
    echo "已连接的 USB 设备："
    for dev in /sys/bus/usb/devices/*; do
        if [ -f "$dev/idVendor" ] && [ -f "$dev/idProduct" ]; then
            vendor=$(cat "$dev/idVendor" 2>/dev/null)
            product=$(cat "$dev/idProduct" 2>/dev/null)
            manufacturer=$(cat "$dev/manufacturer" 2>/dev/null)
            echo "  $vendor:$product - $manufacturer"
        fi
    done
    exit 1
fi

