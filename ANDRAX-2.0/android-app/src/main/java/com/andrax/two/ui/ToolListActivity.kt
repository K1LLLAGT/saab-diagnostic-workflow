package com.andrax.two.ui

import android.content.Intent
import android.os.Bundle
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.andrax.two.data.ToolRepository
import com.andrax.two.model.Tool

/**
 * Shows the tools inside one category. Tapping a tool opens ToolDetailActivity.
 */
class ToolListActivity : AppCompatActivity() {

    companion object { const val EXTRA_CATEGORY_ID = "category_id" }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val catId = intent.getStringExtra(EXTRA_CATEGORY_ID) ?: run { finish(); return }
        val category = ToolRepository.category(this, catId) ?: run { finish(); return }
        title = category.name

        val recycler = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@ToolListActivity)
            layoutParams = RecyclerView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }
        setContentView(recycler)

        recycler.adapter = ToolAdapter(category.tools) { tool ->
            startActivity(
                Intent(this, ToolDetailActivity::class.java)
                    .putExtra(ToolDetailActivity.EXTRA_TOOL_ID, tool.id)
            )
        }
    }

    private class ToolAdapter(
        private val items: List<Tool>,
        private val onClick: (Tool) -> Unit
    ) : RecyclerView.Adapter<ToolAdapter.VH>() {

        class VH(val root: LinearLayout, val name: TextView, val desc: TextView) :
            RecyclerView.ViewHolder(root)

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val ctx = parent.context
            val name = TextView(ctx).apply { textSize = 17f }
            val desc = TextView(ctx).apply { textSize = 13f; alpha = 0.7f }
            val root = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(48, 36, 48, 36)
                addView(name); addView(desc)
            }
            return VH(root, name, desc)
        }

        override fun onBindViewHolder(holder: VH, position: Int) {
            val t = items[position]
            holder.name.text = t.name
            holder.desc.text = t.description
            holder.root.setOnClickListener { onClick(t) }
        }

        override fun getItemCount() = items.size
    }
}
