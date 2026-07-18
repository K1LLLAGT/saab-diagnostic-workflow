package com.andrax.two.launcher

import android.content.Context
import android.content.Intent
import android.net.Uri

/**
 * Bridges the app to the Termux backend.
 *
 * ANDRAX 2.0 does NOT run privileged operations in the app. Instead it asks
 * Termux to execute the scripting-engine entrypoint with arguments, using
 * Termux's documented RUN_COMMAND intent.
 *
 * Prerequisites (one-time, see INSTALL.md):
 *   - Termux installed (F-Droid/GitHub build).
 *   - ~/.termux/termux.properties contains: allow-external-apps=true
 *   - This app granted com.termux.permission.RUN_COMMAND.
 *   - ANDRAX-2.0 extracted at $HOME/ANDRAX-2.0 inside Termux.
 */
object TermuxLauncher {

    private const val TERMUX_PKG = "com.termux"
    private const val RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
    private const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"

    // Absolute path of the engine inside Termux's private storage.
    private const val ENGINE_PATH =
        "/data/data/com.termux/files/home/ANDRAX-2.0/scripting-engine/engine.sh"

    /** Run a tool by id: `engine.sh run-tool <id> -- <args...>`. */
    fun runTool(context: Context, toolId: String, args: List<String> = emptyList()) {
        val argv = mutableListOf("run-tool", toolId)
        if (args.isNotEmpty()) { argv.add("--"); argv.addAll(args) }
        dispatch(context, argv)
    }

    /** Run a workflow by id: `engine.sh run-workflow <id> -- <args...>`. */
    fun runWorkflow(context: Context, workflowId: String, args: List<String> = emptyList()) {
        val argv = mutableListOf("run-workflow", workflowId)
        if (args.isNotEmpty()) { argv.add("--"); argv.addAll(args) }
        dispatch(context, argv)
    }

    /**
     * Fire the RUN_COMMAND intent. Termux opens a session and runs the engine,
     * showing live output to the user. We run in the foreground session
     * (background=false) so the operator can watch and interact.
     */
    private fun dispatch(context: Context, argv: List<String>) {
        val intent = Intent().apply {
            setClassName(TERMUX_PKG, RUN_COMMAND_SERVICE)
            action = ACTION_RUN_COMMAND
            putExtra("com.termux.RUN_COMMAND_PATH", ENGINE_PATH)
            putExtra("com.termux.RUN_COMMAND_ARGUMENTS", argv.toTypedArray())
            putExtra("com.termux.RUN_COMMAND_WORKDIR",
                "/data/data/com.termux/files/home/ANDRAX-2.0")
            putExtra("com.termux.RUN_COMMAND_BACKGROUND", false)
            putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0")
        }
        try {
            context.startForegroundService(intent)
        } catch (e: Exception) {
            // Termux not installed or permission not granted — send the user
            // to install/configure it. See INSTALL.md.
            promptInstallTermux(context)
        }
    }

    private fun promptInstallTermux(context: Context) {
        val fdroid = Intent(
            Intent.ACTION_VIEW,
            Uri.parse("https://f-droid.org/packages/com.termux/")
        )
        context.startActivity(fdroid)
    }
}
