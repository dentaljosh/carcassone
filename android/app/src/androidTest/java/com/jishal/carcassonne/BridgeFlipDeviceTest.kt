package com.jishal.carcassonne

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.BeforeClass
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters
import java.io.File

/**
 * ON-DEVICE ACCEPTANCE for the 2026-08-01 flip (Joshua: "2 yes").
 *
 * Distinct from `RustPortDeviceTest` on purpose. That one gates the PORT — it
 * drives `carc_p7_probe`, a measurement module, and asks "is the Rust core
 * correct and fast enough on this hardware". This one gates the SHIPPED APP: it
 * drives `android_bridge` exactly as the Kotlin UI does, and asks "does the
 * thing the user will hold actually play the champion of record on the Rust
 * backend, and does its save record say so honestly".
 *
 * It has to run in the app process for the same reason G7 did: the resolution
 * under test IS the device's — `carc_rs` as pip resolved it for this ABI, the
 * bundled `PRODUCTION.yaml` as Chaquopy packaged it, and `android_exp_fma()`
 * reading this ISA. A desktop run of the same bridge proves the wiring; only
 * this proves the artefact.
 *
 * Bars are asserted where a miss would mean the flip is WRONG (backend, budget,
 * start rule, save fidelity) and reported where a miss is a finding (s/move).
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class BridgeFlipDeviceTest {

    private fun bridge(): PyObject = Python.getInstance().getModule(MODULE)

    private fun call(fn: String, vararg args: Any?): JSONObject {
        val raw = bridge().callAttr(fn, *args).toString()
        val o = JSONObject(raw)
        assertTrue("$fn failed: $raw", o.optBoolean("ok", false))
        return o
    }

    private fun emit(name: String, json: String) {
        val dir = File(appCtx().getExternalFilesDir(null), "flip").apply { mkdirs() }
        File(dir, "$name.json").writeText(json)
        Log.i(TAG, "$name = ${json.take(4000)}")
    }

    /**
     * Leg 1 — what the app resolved. The DEFAULT is under test, so the game is
     * started with an EMPTY config: anything passed here would be testing the
     * argument rather than the shipped default.
     */
    @Test
    fun t01_default_game_is_the_rust_champion_of_record() {
        call("reset")
        val st = call("new_game", "{}")
        val info = call("runtime_info")
        val budget = call("production_budget")
        emit("flip_resolution", JSONObject(mapOf(
            "backend" to st.optString("backend"),
            "backend_note" to st.opt("backend_note"),
            "budget_note" to st.opt("budget_note"),
            "rust" to info.getJSONObject("rust"),
            "budget" to budget,
        ).toMap()).toString())

        assertEquals("the shipped default must be the rust backend",
            "rust", st.getString("backend"))
        assertTrue("a degraded session left a note: ${st.opt("backend_note")}",
            st.isNull("backend_note"))
        assertEquals("rust", info.getJSONObject("rust").getString("default_backend"))
        assertTrue(info.getJSONObject("rust").getBoolean("active"))

        // THE UNPIN: the phone runs the champion of record, not a carve-out.
        assertEquals(11008, budget.getInt("total_sims"))
        assertEquals(budget.getInt("champion_of_record_total_sims"),
            budget.getInt("total_sims"))
        assertEquals(8, budget.getInt("k_dets"))
        assertEquals(1376, budget.getInt("sims_per_det"))
        assertTrue("the mobile profile must come from the bundled YAML",
            budget.getBoolean("profile_from_yaml"))

        // Full budget => NO runtime_budget_override. Its ABSENCE is the E4 signal
        // that a game was played at champion strength, so it is asserted, not read.
        val man = call("get_manifest").getJSONObject("manifest")
        assertTrue("a full-budget game must carry no runtime_budget_override",
            !man.has("runtime_budget_override"))
        assertTrue("the mobile profile is not below the champion any more",
            st.isNull("budget_note"))
    }

    /**
     * Leg 2 — the retail start tile is pre-placed before anyone draws, AND it
     * sits on the RECENTRED grid (2026-08-02, app-only).
     *
     * Row 18 of 35, not row 6: the walled grid left 6 rows of headroom above and
     * 28 below, which is what produced the "invisible border" Joshua hit on this
     * very device — a rule-legal placement above row 0 is silently never offered.
     * The shift is 12, i.e. EVEN, which is what makes it representation-neutral
     * (tests/test_start_tile_grid_bound.py). Asserted, not reported: a miss here
     * means the shipped app is back on the walled grid.
     */
    @Test
    fun t02_new_game_starts_from_the_retail_tile_on_the_centred_grid() {
        call("reset")
        val st = call("new_game", "{}")
        val board = st.getJSONArray("board")
        assertEquals("retail: exactly one tile is pre-placed", 1, board.length())
        val tile = board.getJSONObject(0)
        assertEquals("the app default grid is centered18", 18, tile.getInt("row"))
        assertEquals(15, tile.getInt("col"))
        // Every legal first placement is clear of the top wall by a mile.
        val cells = st.getJSONObject("legal").getJSONArray("tile_cells")
        var minRow = Int.MAX_VALUE
        for (i in 0 until cells.length()) {
            minRow = minOf(minRow, cells.getJSONObject(i).getInt("row"))
        }
        assertTrue("lowest legal row was $minRow; the top wall is at 0", minRow >= 17)
        // Nobody spends a turn on it and no meeple goes on it.
        assertEquals("retail: the start tile carries no meeple",
            0, st.getJSONArray("meeples").length())
        assertEquals("[7,7]", st.getJSONArray("meeples_free").toString())
        assertEquals("retail: the deck is the remaining 71", 71,
            st.getInt("tiles_remaining"))
        emit("flip_start_tile", JSONObject(mapOf(
            "description" to tile.getString("description"),
            "row" to tile.getInt("row"), "col" to tile.getInt("col"),
            "tiles_remaining" to st.getInt("tiles_remaining"),
        ).toMap()).toString())
        Log.w(TAG, "start tile = ${tile.getString("description")} " +
            "@(${tile.getInt("row")},${tile.getInt("col")})")
    }

    /**
     * Leg 3 — real champion moves at the real budget, timed. The bar is G7's
     * (<=2 s); reported, not asserted, because a slow move is a finding for the
     * write-up and a red test here would hide legs 4's save evidence.
     */
    @Test
    fun t03_champion_moves_at_the_full_budget() {
        call("reset")
        var st = call("new_game", """{"human_player": 0}""")
        val times = mutableListOf<Double>()
        var guard = 0
        while (times.size < N_MOVES && guard++ < 40 && !st.getBoolean("is_terminated")) {
            st = if (st.getBoolean("is_human_turn")) {
                call("apply_action",
                    st.getJSONObject("legal").getJSONArray("action_ids").getInt(0))
            } else {
                val t0 = System.nanoTime()
                val r = call("ai_move")
                times += (System.nanoTime() - t0) / 1e9
                r
            }
        }
        assertTrue("no champion move was played", times.size >= N_MOVES)
        val sorted = times.sorted()
        val median = sorted[sorted.size / 2]
        emit("flip_s_per_move", JSONObject(mapOf(
            "s_per_move" to times, "median" to median,
            "total_sims" to 11008, "threads" to 4,
        ).toMap()).toString())
        Log.w(TAG, "champion s/move = $times median=$median (G7 ref 1.551, bar 2.0)")
    }

    /**
     * Leg 4 — the save record is honest and lossless. `start_rule` and the budget
     * fields have to survive, because `(deck_seed, actions)` only reproduces a
     * game under the rules it was played under.
     */
    @Test
    fun t04_save_restore_round_trip_carries_the_new_truth() {
        call("reset")
        var st = call("new_game", """{"seed": 909, "human_player": 0}""")
        var guard = 0
        var aiMoves = 0
        while (aiMoves < 2 && guard++ < 30 && !st.getBoolean("is_terminated")) {
            st = if (st.getBoolean("is_human_turn")) {
                call("apply_action",
                    st.getJSONObject("legal").getJSONArray("action_ids").getInt(0))
            } else { aiMoves++; call("ai_move") }
        }
        val save = call("save_game")
        assertEquals("retail", save.getString("start_rule"))
        assertEquals("the save must record WHICH GRID the game was played on",
            "centered18", save.getString("grid_rule"))
        assertEquals("the save must record the UNPLACEABLE-TILE rule",
            "redraw", save.getString("draw_rule"))
        assertEquals("the save must record the CLOISTER SCAN rule",
            "fixed", save.getString("cloister_rule"))
        assertEquals("the save must record WHICH FARM DATA the game used",
            "r9", save.getString("farm_rule"))
        assertEquals("the five rule fields must label as the Phase-B bundle",
            "fixed_v1", save.getString("rules_profile"))
        assertTrue("the save must stamp the champion identity",
            save.getString("leaf_hash").isNotEmpty())

        val before = call("get_state")
        val restored = call("restore_game", save.toString())
        val after = call("get_state")
        assertEquals(before.getJSONArray("scores").toString(),
            after.getJSONArray("scores").toString())
        assertEquals(before.getInt("n_actions"), after.getInt("n_actions"))
        assertEquals(before.getString("phase"), after.getString("phase"))
        assertEquals("a restore must stay on the rust backend",
            "rust", after.getString("backend"))
        emit("flip_save_round_trip", JSONObject(mapOf(
            "start_rule" to save.getString("start_rule"),
            "grid_rule" to save.getString("grid_rule"),
            "draw_rule" to save.getString("draw_rule"),
            "cloister_rule" to save.getString("cloister_rule"),
            "farm_rule" to save.getString("farm_rule"),
            "rules_profile" to save.getString("rules_profile"),
            "leaf_hash" to save.getString("leaf_hash"),
            "champion_id" to save.getString("champion_id"),
            "n_actions" to after.getInt("n_actions"),
            "ai_decisions" to restored.getJSONObject("restored").getInt("ai_decisions"),
            "scores" to after.getJSONArray("scores").toString(),
        ).toMap()).toString())
    }

    /**
     * Leg 5 — THE BACKWARD-COMPAT LEG for the 2026-08-02 recentring.
     *
     * The two real E4 archives are the only human-vs-champion games that exist.
     * They were written by an app that had neither `grid_rule` nor the recentred
     * grid, so the ABSENT field must mean "engine6" forever — and it has to mean
     * that on the DEVICE, through the same `restore_game` the Past-games list
     * calls, not just in a desktop test. If it silently resolved to the new
     * default instead, the identical action log would decode different board
     * cells (an action index is a WINDOW cell) and the replay would either
     * diverge on score or be outright illegal. Unrecoverable data, so asserted.
     */
    @Test
    fun t05_old_archives_still_replay_on_the_walled_grid() {
        val names = listOf("1785205383_867966", "1785466497_161583")
        val report = mutableMapOf<String, Any>()
        for (name in names) {
            call("reset")
            val blob = JSONObject(asset("e4/$name.json").readText())
            assertTrue("fixture is not a pre-recentring archive",
                !blob.has("grid_rule") && !blob.has("start_rule"))
            assertTrue("fixture is not a pre-fixed_v1 archive",
                !blob.has("draw_rule") && !blob.has("cloister_rule") &&
                    !blob.has("farm_rule") && !blob.has("rules_profile"))
            val restored = call("restore_game", blob.toString())
            val st = call("get_state")
            assertEquals("$name: replay diverged",
                blob.getJSONArray("scores").toString(),
                st.getJSONArray("scores").toString())
            assertEquals("$name: not every action replayed",
                blob.getJSONArray("actions").length(),
                restored.getJSONObject("restored").getInt("actions"))
            // The grid the archive replayed on, read back the way the payload
            // records it: a fresh save of the restored session.
            val save = call("save_game")
            assertEquals("$name: an archive with no grid_rule must be engine6",
                "engine6", save.getString("grid_rule"))
            assertEquals("$name: an archive with no start_rule must be engine",
                "engine", save.getString("start_rule"))
            assertEquals("$name: an archive with no draw_rule must be engine",
                "engine", save.getString("draw_rule"))
            assertEquals("$name: an archive with no cloister_rule must be drifting",
                "drifting", save.getString("cloister_rule"))
            // The FARM rule is process-global (bridge block 1a), so this archive
            // cannot be replayed on its own tile data here — the app process is
            // latched to R9. It was replayed ACROSS the rule and then proved
            // identical against the record's own stored result, which is what the
            // score assertion above IS. The note is the audit trail for that.
            assertEquals("$name: the record still says which farm data it used",
                "engine", save.getString("farm_rule"))
            assertEquals("$name: all five legacy values are the walled engine",
                "walled", save.getString("rules_profile"))
            val note = restored.getJSONObject("restored").optString("rules_note", "")
            assertTrue("$name: a cross-rule replay must say so: '$note'",
                note.contains("verified identical", ignoreCase = true))
            report[name] = JSONObject(mapOf(
                "scores" to st.getJSONArray("scores").toString(),
                "actions" to restored.getJSONObject("restored").getInt("actions"),
                "grid_rule" to save.getString("grid_rule"),
                "start_rule" to save.getString("start_rule"),
                "draw_rule" to save.getString("draw_rule"),
                "cloister_rule" to save.getString("cloister_rule"),
                "farm_rule" to save.getString("farm_rule"),
                "rules_profile" to save.getString("rules_profile"),
                "rules_note" to note,
            ).toMap())
        }
        emit("grid_legacy_archives", JSONObject(report.toMap()).toString())
    }

    /**
     * Leg 6 — THE FIXED_V1 FLIP, on the device, end to end.
     *
     * Legs 2 and 4 cover the grid and the save fields; this one asserts the two
     * levers that have no visible signature on move 1 — the redraw rule and the
     * fixed cloister scan reach BOTH engines (the Python one the UI runs on and
     * the Rust mirror the champion searches with) — plus the one that cannot be
     * a per-game argument at all.
     *
     * `farm_rule` is the interesting assertion. It is latched from
     * `CARCASSONNE_FIX_R9` before the first import and memoised in a Rust
     * `OnceLock`, so "the phone is on the R9 farm data" is a property of the
     * PROCESS, not of any game object — and the only place it can be read back is
     * the engine itself. A miss here means the app is stamping `fixed_v1` on
     * games played with the unfixed field-through-a-city data.
     */
    @Test
    fun t06_new_games_play_the_full_fixed_v1_bundle() {
        call("reset")
        val info = call("runtime_info")
        val rules = info.getJSONObject("rules")
        assertEquals("a new app game must be the whole Phase-B bundle",
            "fixed_v1", rules.getString("new_game_profile"))
        assertEquals("redraw", rules.getString("draw_rule"))
        assertEquals("fixed", rules.getString("cloister_rule"))
        assertEquals("the R9 farm fix must have latched in THIS process",
            "r9", rules.getString("farm_rule_latched"))
        assertTrue("the requested farm rule was not the one that latched",
            rules.getBoolean("farm_rule_ok"))

        // Reaching the engines, not just the record. `new_game` with an empty
        // config again: the DEFAULT is what ships.
        val st = call("new_game", "{}")
        assertEquals("fixed_v1", call("save_game").getString("rules_profile"))
        // The rust mirror is live and agrees with the Python board byte for byte
        // (`_assert_mirror` runs at game start and before every decision, so an
        // active mirror IS the agreement claim for these rule flags).
        assertEquals("rust", st.getString("backend"))
        assertTrue("the mirror must be live for the flags to have reached it",
            call("runtime_info").getJSONObject("rust").getBoolean("active"))
        emit("fixed_v1_rules", rules.toString())
        Log.w(TAG, "rules = $rules")
    }

    companion object {
        private const val TAG = "FlipDevice"
        private const val MODULE = "android_bridge"
        private const val N_MOVES = 3

        private fun appCtx() =
            InstrumentationRegistry.getInstrumentation().targetContext

        /** Copy an androidTest asset out to a readable file (same trick as P7). */
        private fun asset(path: String): File {
            val out = File(appCtx().cacheDir, "flipassets/$path")
            if (out.isFile && out.length() > 0) return out
            out.parentFile?.mkdirs()
            InstrumentationRegistry.getInstrumentation().context.assets.open(path)
                .use { input -> out.outputStream().use { input.copyTo(it) } }
            return out
        }

        @BeforeClass
        @JvmStatic
        fun startPython() {
            if (!Python.isStarted()) {
                Python.start(com.chaquo.python.android.AndroidPlatform(appCtx()))
            }
        }
    }
}
