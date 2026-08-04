package com.saabsuite.transport

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.os.Build
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/**
 * USB-OTG passthrough transport for a J2534-class adapter (e.g. a
 * Mongoose-compatible device with a USB-serial or USB-bulk interface).
 *
 * Mirrors the open/connect/read/write/disconnect/close lifecycle used by
 * src/j2534/simulator.py so the same higher-level UDS/sniffer/flashing
 * logic can eventually target either transport.
 *
 * This talks to whatever vendor/product ID the adapter reports over raw
 * USB bulk transfer; it does not implement a specific vendor's USB
 * protocol framing (that lives in a device-specific driver layered on
 * top, analogous to plugins/<oem>/plugin.py on the OEM side).
 */
class UsbOtgTransport(private val context: Context) {

    companion object {
        const val ACTION_USB_PERMISSION = "com.saabsuite.USB_PERMISSION"
        const val DEFAULT_TIMEOUT_MS = 1000
    }

    private val usbManager: UsbManager by lazy {
        context.getSystemService(Context.USB_SERVICE) as UsbManager
    }

    private var device: UsbDevice? = null
    private var connection: UsbDeviceConnection? = null
    private var usbInterface: UsbInterface? = null
    private var endpointIn: UsbEndpoint? = null
    private var endpointOut: UsbEndpoint? = null

    /** Enumerate attached USB devices that look like a J2534-class adapter
     * (vendor-specific interface class). Filter further by VID/PID for a
     * known device family in a real deployment. */
    fun discoverDevices(): List<UsbDevice> =
        usbManager.deviceList.values.filter { dev ->
            (0 until dev.interfaceCount).any { i ->
                dev.getInterface(i).interfaceClass == UsbConstantsVendorSpecific
            }
        }

    /** Request runtime USB permission for [device] (required before opening
     * a connection on API 26+). Suspends until the user responds or the
     * request errors. */
    suspend fun requestPermission(device: UsbDevice): Boolean = suspendCancellableCoroutine { cont ->
        val permissionIntent = PendingIntent.getBroadcast(
            context, 0, Intent(ACTION_USB_PERMISSION),
            PendingIntent.FLAG_MUTABLE
        )
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                if (intent.action == ACTION_USB_PERMISSION) {
                    context.unregisterReceiver(this)
                    val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
                    if (cont.isActive) cont.resume(granted)
                }
            }
        }
        // ACTION_USB_PERMISSION is our own private broadcast — not exported to other apps.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(receiver, IntentFilter(ACTION_USB_PERMISSION), Context.RECEIVER_NOT_EXPORTED)
        } else {
            context.registerReceiver(receiver, IntentFilter(ACTION_USB_PERMISSION))
        }
        usbManager.requestPermission(device, permissionIntent)
    }

    /** open() — claim the device's vendor-specific interface and locate
     * bulk in/out endpoints. */
    fun open(target: UsbDevice): Boolean {
        val conn = usbManager.openDevice(target) ?: return false
        val iface = (0 until target.interfaceCount)
            .map { target.getInterface(it) }
            .firstOrNull { it.interfaceClass == UsbConstantsVendorSpecific }
            ?: return false

        if (!conn.claimInterface(iface, true)) return false

        endpointIn = (0 until iface.endpointCount)
            .map { iface.getEndpoint(it) }
            .firstOrNull { it.direction == android.hardware.usb.UsbConstants.USB_DIR_IN }
        endpointOut = (0 until iface.endpointCount)
            .map { iface.getEndpoint(it) }
            .firstOrNull { it.direction == android.hardware.usb.UsbConstants.USB_DIR_OUT }

        device = target
        connection = conn
        usbInterface = iface
        return endpointIn != null && endpointOut != null
    }

    /** connect() is a no-op at the USB layer beyond open() — protocol
     * (CAN/ISO15765/etc.) selection happens in the framing the adapter
     * expects, sent as the first write() payload by the higher-level
     * J2534 client this transport backs. */

    fun write(data: ByteArray, timeoutMs: Int = DEFAULT_TIMEOUT_MS): Int {
        val conn = connection ?: throw IllegalStateException("Not open — call open() first")
        val ep = endpointOut ?: throw IllegalStateException("No OUT endpoint")
        return conn.bulkTransfer(ep, data, data.size, timeoutMs)
    }

    fun read(maxLength: Int = 512, timeoutMs: Int = DEFAULT_TIMEOUT_MS): ByteArray? {
        val conn = connection ?: throw IllegalStateException("Not open — call open() first")
        val ep = endpointIn ?: throw IllegalStateException("No IN endpoint")
        val buffer = ByteArray(maxLength)
        val n = conn.bulkTransfer(ep, buffer, buffer.size, timeoutMs)
        return if (n > 0) buffer.copyOf(n) else null
    }

    fun disconnect() {
        usbInterface?.let { connection?.releaseInterface(it) }
        endpointIn = null
        endpointOut = null
    }

    fun close() {
        disconnect()
        connection?.close()
        connection = null
        device = null
    }
}

// USB interface class used by most vendor-specific J2534/serial adapters.
private const val UsbConstantsVendorSpecific = 0xFF
