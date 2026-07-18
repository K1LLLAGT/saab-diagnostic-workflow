package com.andrax.two.ui

import android.os.Bundle
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.andrax.two.data.ToolRepository
import com.andrax.two.launcher.TermuxLauncher

/**
 * Tool detail screen: name, description, an example, an argument field, and a
 * "Run in Termux" button that dispatches to the backend via TermuxLauncher.
 */
class ToolDetailActivity : AppCompatActivity() {

    companion object { const val EXTRA_TOOL_ID = "tool_id" }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val toolId = intent.getStringExtra(EXTRA_TOOL_ID) ?: run { finish(); return }
        val tool = ToolRepository.tool(this, toolId) ?: run { finish(); return }
        title = tool.name

        val pad = 48
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }

        root.addView(TextView(this).apply {
            text = tool.description
            textSize = 16f
        })

        root.addView(TextView(this).apply {
            text = "\nExample:\n  andrax ${tool.example}"
            textSize = 13f
            alpha = 0.7f
            setTextIsSelectable(true)
        })

        val argsField = EditText(this).apply {
            hint = "arguments (e.g. -sV scanme.nmap.org)"
            inputType = InputType.TYPE_CLASS_TEXT
        }
        root.addView(TextView(this).apply { text = "\nArguments:" })
        root.addView(argsField)

        root.addView(Button(this).apply {
            text = "Run in Termux"
            setOnClickListener {
                val raw = argsField.text.toString().trim()
                // Naive tokenizer for the prototype. A production build should
                // use a proper shell-aware splitter and validate/escape input.
                val args = if (raw.isEmpty()) emptyList()
                           else raw.split(Regex("\\s+"))
                TermuxLauncher.runTool(this@ToolDetailActivity, tool.id, args)
                Toast.makeText(
                    this@ToolDetailActivity,
                    "Launching ${tool.name} in Termux…",
                    Toast.LENGTH_SHORT
                ).show()
            }
        })

        setContentView(root)
    }
}
