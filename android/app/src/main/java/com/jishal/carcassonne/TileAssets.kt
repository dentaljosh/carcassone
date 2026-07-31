package com.jishal.carcassonne

import android.content.Context
import android.content.res.AssetManager
import android.graphics.BitmapFactory
import android.util.Log
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.produceState
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Every tile face and meeple sprite, decoded once.
 *
 * Loaded eagerly off the main thread (32 faces at 416x416 ~= 22 MB) rather than
 * lazily inside `DrawScope`: decoding during a draw pass is the classic source
 * of first-frame jank, and the board redraws on every pan frame.
 *
 * Asset paths mirror the bridge's `image` field verbatim:
 * `"base_game/Base_Game_C2_Tile_A.png"` -> `"tiles/base_game/..."`.
 */
class TileAssets(
    private val tiles: Map<String, ImageBitmap>,
    private val sprites: Map<String, ImageBitmap>,
) {
    fun tile(image: String?): ImageBitmap? = image?.let { tiles[it] }

    fun sprite(name: String): ImageBitmap? = sprites[name]

    /**
     * Meeple sprite for a seat. Blue is always the human, red always the
     * champion, whichever engine seat index each happens to hold.
     */
    fun meeple(player: Int, humanPlayer: Int): ImageBitmap? =
        sprite(if (player == humanPlayer) "blue_meeple.png" else "red_meeple.png")

    companion object {
        private const val TAG = "TileAssets"
        private const val ROOT = "tiles"

        private val SPRITE_FILES = listOf(
            "blue_meeple.png", "red_meeple.png", "green_meeple.png",
            "yellow_meeple.png", "black_meeple.png", "pink_meeple.png",
            "Empty.png",
        )

        suspend fun load(context: Context): TileAssets = withContext(Dispatchers.IO) {
            val am = context.assets
            val tiles = HashMap<String, ImageBitmap>()
            for (dir in listOf("base_game")) {
                val names = runCatching { am.list("$ROOT/$dir") }.getOrNull().orEmpty()
                for (name in names) {
                    if (!name.endsWith(".png")) continue
                    // The key is exactly what the bridge reports (os.path.join on
                    // the device is POSIX, so always a forward slash).
                    decode(am, "$ROOT/$dir/$name")?.let { tiles["$dir/$name"] = it }
                }
            }
            val sprites = HashMap<String, ImageBitmap>()
            for (name in SPRITE_FILES) decode(am, "$ROOT/$name")?.let { sprites[name] = it }
            Log.i(TAG, "loaded ${tiles.size} tile faces, ${sprites.size} sprites")
            TileAssets(tiles, sprites)
        }

        private fun decode(am: AssetManager, path: String): ImageBitmap? = runCatching {
            am.open(path).use { BitmapFactory.decodeStream(it) }?.asImageBitmap()
        }.onFailure { Log.w(TAG, "asset missing: $path", it) }.getOrNull()
    }
}

/** `null` until the decode finishes; the board shows a spinner meanwhile. */
@Composable
fun rememberTileAssets(): State<TileAssets?> {
    val context = LocalContext.current
    return produceState<TileAssets?>(initialValue = null, context) {
        value = TileAssets.load(context)
    }
}

/**
 * Board palette. Terrain colours are a straight port of `TERRAIN_COLOR` in
 * `scripts/play_vs_tier1_gui.py` so the phone and the desktop tool read the
 * same; player colours are ours.
 */
object CarcColors {
    val Human = Color(0xFF2E6FD4)      // blue meeple
    val Ai = Color(0xFFC43C3C)         // red meeple

    val City = Color(0xFFC43C3C)
    val Road = Color(0xFF8B6F47)
    val Grass = Color(0xFF4CAF50)
    val Chapel = Color(0xFFF5C518)
    val DefaultDot = Color(0xFF888888)

    val LegalCell = Color(0xFF3DDC84)
    val SelectedCell = Color(0xFFFFC107)
    val AiLastTile = Color(0xFFC43C3C)
    val BoardBackdrop = Color(0xFF1D2A22)

    /**
     * The ring around a farmer slot's diamond. Earth-toned rather than the white
     * every other dot wears: shape alone was carrying the distinction, and at a
     * whole-board fit a small rotated square and a small circle are the same
     * handful of pixels.
     */
    val FarmerRing = Color(0xFF5A3E1B)

    /**
     * A feature the engine scores for BOTH seats (a meeple tie). SUPERSEDED as the
     * board rendering 2026-07-31 — contested regions now draw alternating stripes in
     * the two player colours (`BoardCanvas.shadeRegionContested`; Joshua: "the purple
     * is too subtle"). Kept for any legend/HUD use that wants a single swatch.
     */
    val Contested = Color(0xFF8E44AD)

    /** Engine `TerrainType.name` (uppercase) -> dot colour. */
    fun terrain(name: String): Color = when (name.uppercase()) {
        "CITY" -> City
        "ROAD" -> Road
        "GRASS" -> Grass
        "CHAPEL", "FLOWERS" -> Chapel
        else -> DefaultDot
    }

    fun player(player: Int, humanPlayer: Int): Color =
        if (player == humanPlayer) Human else Ai
}
