package com.saabsuite.transport

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okhttp3.Response
import org.json.JSONObject
import kotlin.math.min

/**
 * Remote CAN gateway client — see android/transport/RemoteCanProtocol.md
 * for the wire format. Backs a vehicle bus reachable through
 * backend/app/websocket_remote.py instead of a local USB adapter, e.g.
 * when the phone is used purely as a remote diagnostics viewer/controller.
 */
class RemoteCanTransport(
    private val wsUrl: String,
    private val accessToken: String,
    private val scope: CoroutineScope,
) {
    private val client = OkHttpClient()
    private var socket: WebSocket? = null
    val incoming = Channel<JSONObject>(capacity = 256)

    private var reconnectAttempt = 0

    fun connect() {
        val request = Request.Builder()
            .url("$wsUrl?token=$accessToken")
            .build()
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectAttempt = 0
                sendCommand("open_gateway", mapOf("protocol" to "ISO15765", "baud" to 500000))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                scope.launch { incoming.send(JSONObject(text)) }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                scope.launch { connectWithRetry() }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                scope.launch { connectWithRetry() }
            }
        })
    }

    /** Exponential backoff: 1s, 2s, 4s, ... capped at 30s. */
    suspend fun connectWithRetry() {
        reconnectAttempt++
        val delayMs = min(1000L * (1 shl (reconnectAttempt - 1)), 30_000L)
        delay(delayMs)
        connect()
    }

    fun sendCanFrame(arbId: Int, data: ByteArray, protocol: String = "ISO15765") {
        val payload = JSONObject().apply {
            put("id", "0x" + arbId.toString(16).uppercase())
            put("data", data.joinToString("") { "%02X".format(it) })
            put("dlc", data.size)
            put("protocol", protocol)
        }
        send("can_frame", payload)
    }

    fun sendChat(author: String, text: String) {
        send("chat", JSONObject().apply { put("author", author); put("text", text) })
    }

    fun sendCommand(command: String, args: Map<String, Any> = emptyMap()) {
        val payload = JSONObject().apply {
            put("command", command)
            put("args", JSONObject(args))
        }
        send("remote_command", payload)
    }

    private fun send(type: String, payload: JSONObject) {
        val message = JSONObject().apply {
            put("type", type)
            put("payload", payload)
            put("ts", System.currentTimeMillis() / 1000.0)
        }
        socket?.send(message.toString())
    }

    fun close() {
        sendCommand("close_gateway")
        socket?.close(1000, "client closing")
    }
}
