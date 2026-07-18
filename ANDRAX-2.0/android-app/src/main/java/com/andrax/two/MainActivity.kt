package com.andrax.two

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.andrax.two.ui.CategoryListActivity

/**
 * Entry point. Keeps startup trivial and forwards to the category browser.
 * A real build might show a splash / authorization acknowledgement here.
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        startActivity(Intent(this, CategoryListActivity::class.java))
        finish()
    }
}
