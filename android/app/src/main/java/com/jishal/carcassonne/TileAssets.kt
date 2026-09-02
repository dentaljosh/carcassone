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

        /**
         * The seven sprites drawn directly out of `assets/tiles/`.
         *
         * All six meeple colours ship even though the 2p scope only ever draws blue
         * and red: they are one file each, and a colour that is missing the day a
         * third seat exists is a crash, not a design change.
         */
        val SPRITE_FILES: List<String> = listOf(
            "blue_meeple.png", "red_meeple.png", "green_meeple.png",
            "yellow_meeple.png", "black_meeple.png", "pink_meeple.png",
            "Empty.png",
        )

        /**
         * The 24 lettered base-game faces, `A`..`X`.
         *
         * Named rather than discovered, because "discover whatever is in the
         * directory" is exactly how a build shipped with a partial asset tree — the
         * loader listed the directory, found fewer files than it should have, and
         * said nothing. See [load].
         */
        val LETTERED_TILE_FACES: List<String> =
            ('A'..'X').map { "base_game/Base_Game_C2_Tile_$it.png" }

        /**
         * The 8 garden ("Abbot-…_Garden") art variants.
         *
         * They are *art* variants — under the locked 2p Base+Farmers scope a garden
         * carries no rule at all, which is why `android_bridge.tile_type_key` merges
         * each of these with its plain twin in the bag view. They are still separate
         * engine faces with their own `image`, so the file must be present or those
         * tiles draw blank.
         */
        val GARDEN_TILE_FACES: List<String> = listOf("E", "H", "I", "M", "N", "R", "U", "V")
            .map { "base_game/Abbot-Base_Game_C2_Tile_${it}_Garden.png" }

        /** Every tile face the bridge can name: 24 lettered + 8 garden = 32. */
        val REQUIRED_TILE_FACES: List<String> = LETTERED_TILE_FACES + GARDEN_TILE_FACES

        /** Everything that must decode for the board to render: 32 + 7 = 39. */
        val REQUIRED_ASSETS: List<String> =
            REQUIRED_TILE_FACES.map { "$ROOT/$it" } + SPRITE_FILES.map { "$ROOT/$it" }

        /**
         * Decode every required sprite, or THROW.
         *
         * ⚠️ This used to no-op on a missing decode: `decode` logged a warning and
         * returned null, the map simply came up short, and the app launched into a
         * board of blank squares. `assets/` is git-ignored and generated
         * (`tools/prepare_assets.py`), so an incomplete tree is a routine mistake —
         * on 2026-09-02 a worktree build shipped with only `base_game/` copied and
         * every meeple sprite absent, and nothing failed until it was on the phone.
         * The Gradle `checkTileAssets` task only counts `base_game/`, so it could
         * not see it either.
         *
         * Failing here costs a crash on a build that was already broken, and buys a
         * message that names the missing file.
         */
        suspend fun load(context: Context): TileAssets = withContext(Dispatchers.IO) {
            val am = context.assets
            val tiles = HashMap<String, ImageBitmap>()
            val missing = ArrayList<String>()
            for (name in REQUIRED_TILE_FACES) {
                // The key is exactly what the bridge reports (os.path.join on
                // the device is POSIX, so always a forward slash).
                val bmp = decode(am, "$ROOT/$name")
                if (bmp == null) missing += "$ROOT/$name" else tiles[name] = bmp
            }
            val sprites = HashMap<String, ImageBitmap>()
            for (name in SPRITE_FILES) {
                val bmp = decode(am, "$ROOT/$name")
                if (bmp == null) missing += "$ROOT/$name" else sprites[name] = bmp
            }
            if (missing.isNotEmpty()) {
                throw IllegalStateException(
                    "${missing.size} of ${REQUIRED_ASSETS.size} required tile assets " +
                        "are missing or undecodable: ${missing.joinToString(", ")}. " +
                        "assets/ is git-ignored — regenerate it with " +
                        "`.venv/bin/python android/tools/prepare_assets.py`, and if " +
                        "you are building in a worktree copy the WHOLE " +
                        "android/app/src/main/assets/ tree across, not just " +
                        "assets/tiles/base_game/."
                )
            }
            Log.i(TAG, "loaded ${tiles.size} tile faces, ${sprites.size} sprites")
            TileAssets(tiles, sprites)
        }

        private fun decode(am: AssetManager, path: String): ImageBitmap? = runCatching {
            am.open(path).use { BitmapFactory.decodeStream(it) }?.asImageBitmap()
        }.onFailure { Log.e(TAG, "asset missing: $path", it) }.getOrNull()
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
