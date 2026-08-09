package com.jcloisterzone.ai.player;

import java.util.Random;

import com.jcloisterzone.ai.AiPlayer;
import com.jcloisterzone.game.state.GameState;
import com.jcloisterzone.io.message.ReplayableMessage;

import io.vavr.collection.Vector;

/**
 * Ported from JCloisterZone 4.x (com.jcloisterzone.ai.player.DummyAiPlayer).
 * Only deviation: `WsInGameMessage` -> `ReplayableMessage` (D1). Uniform-random legal move; useful as a
 * control opponent. Not used by AiEngine unless explicitly selected.
 */
public class DummyAiPlayer implements AiPlayer {

    private Random random = new Random();

    @Override
    public ReplayableMessage apply(GameState state) {
        Vector<ReplayableMessage> messages = getPossibleActions(state);
        return messages.get(random.nextInt(messages.length()));
    }
}
