package com.andrax.two.model

/**
 * A tool category, mirroring an object in tool_registry.json:
 *   { "id", "name", "icon", "tools": [ ... ] }
 */
data class Category(
    val id: String,
    val name: String,
    val icon: String,
    val tools: List<Tool>
)
