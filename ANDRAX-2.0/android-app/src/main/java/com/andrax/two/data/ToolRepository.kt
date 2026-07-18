package com.andrax.two.data

import android.content.Context
import com.andrax.two.model.Category
import com.andrax.two.model.Tool
import org.json.JSONObject

/**
 * Loads the ANDRAX tool catalog from assets/tool_registry.json.
 *
 * The asset is a byte-for-byte copy of launcher-system/tool_registry.json, so
 * the app and the backend always agree on ids and script paths. Keep them in
 * sync (see INSTALL.md "Keeping the app catalog in sync").
 */
object ToolRepository {

    private var cache: List<Category>? = null

    /** Parse and cache the registry. */
    fun categories(context: Context): List<Category> {
        cache?.let { return it }

        val json = context.assets.open("tool_registry.json")
            .bufferedReader().use { it.readText() }
        val root = JSONObject(json)
        val cats = root.getJSONArray("categories")

        val result = ArrayList<Category>(cats.length())
        for (i in 0 until cats.length()) {
            val c = cats.getJSONObject(i)
            val toolsArr = c.getJSONArray("tools")
            val tools = ArrayList<Tool>(toolsArr.length())
            for (j in 0 until toolsArr.length()) {
                val t = toolsArr.getJSONObject(j)
                tools.add(
                    Tool(
                        id = t.getString("id"),
                        name = t.getString("name"),
                        script = t.getString("script"),
                        description = t.getString("description"),
                        example = t.optString("example", "")
                    )
                )
            }
            result.add(
                Category(
                    id = c.getString("id"),
                    name = c.getString("name"),
                    icon = c.optString("icon", "tool"),
                    tools = tools
                )
            )
        }
        cache = result
        return result
    }

    fun category(context: Context, id: String): Category? =
        categories(context).firstOrNull { it.id == id }

    fun tool(context: Context, id: String): Tool? =
        categories(context).flatMap { it.tools }.firstOrNull { it.id == id }
}
