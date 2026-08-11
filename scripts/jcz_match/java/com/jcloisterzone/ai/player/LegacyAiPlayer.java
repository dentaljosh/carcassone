package com.jcloisterzone.ai.player;

import com.jcloisterzone.Player;
import com.jcloisterzone.ai.GameStateRanking;
import com.jcloisterzone.ai.RankingAiPlayer;

/**
 * Ported from JCloisterZone 4.x (com.jcloisterzone.ai.player.LegacyAiPlayer) to the 5.x API.
 *
 * SEMANTIC DEVIATIONS FROM THE 4.x ORIGINAL
 * -----------------------------------------
 * D2. The whole `supportedSetup()` override (and its `getSupportedCapabilities()` helper listing the 27
 *     capabilities the legacy AI claimed to handle) is DELETED: `com.jcloisterzone.game.SupportedSetup`
 *     and `com.jcloisterzone.Expansion` do not exist in 5.x. Consequence: NOTHING stops this AI from
 *     being seated in a game with a capability it was never written for. The caller must enforce scope.
 *     (For the locked Base+Farmers scope this is vacuous — the 4.x list included StandardGameCapability
 *     and farmers are a Rule, not a capability.)
 * The ranking itself is unchanged: `createStateRanking` still returns `new LegacyRanking(me)`.
 */
public class LegacyAiPlayer extends RankingAiPlayer {

    @Override
    protected GameStateRanking createStateRanking(Player me) {
        return new LegacyRanking(me);
    }
}
