package com.andrax.two.model

/**
 * A single tool entry, mirroring an object in tool_registry.json:
 *   { "id", "name", "script", "description", "example" }
 */
data class Tool(
    val id: String,
    val name: String,
    val script: String,
    val description: String,
    val example: String
)
