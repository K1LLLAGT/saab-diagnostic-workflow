package com.andrax.two.ui

import android.content.Intent
import android.os.Bundle
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.andrax.two.data.ToolRepository
import com.andrax.two.model.Category

/**
 * Top-level ANDRAX-style screen: the list of tool categories
 * (Information Gathering, Vulnerability Analysis, ...). Tapping a category
 * opens ToolListActivity for that category.
 */
class CategoryListActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "ANDRAX 2.0"

        val recycler = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@CategoryListActivity)
            layoutParams = RecyclerView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }
        setContentView(recycler)

        val categories = ToolRepository.categories(this)
        recycler.adapter = CategoryAdapter(categories) { category ->
            startActivity(
                Intent(this, ToolListActivity::class.java)
                    .putExtra(ToolListActivity.EXTRA_CATEGORY_ID, category.id)
            )
        }
    }

    /** Minimal adapter: one row per category. */
    private class CategoryAdapter(
        private val items: List<Category>,
        private val onClick: (Category) -> Unit
    ) : RecyclerView.Adapter<CategoryAdapter.VH>() {

        class VH(val text: TextView) : RecyclerView.ViewHolder(text)

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val tv = TextView(parent.context).apply {
                textSize = 18f
                setPadding(48, 44, 48, 44)
            }
            return VH(tv)
        }

        override fun onBindViewHolder(holder: VH, position: Int) {
            val c = items[position]
            holder.text.text = "${c.name}   (${c.tools.size})"
            holder.text.setOnClickListener { onClick(c) }
        }

        override fun getItemCount() = items.size
    }
}
