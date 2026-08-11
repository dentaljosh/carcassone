package com.jcloisterzone.ai;

import com.jcloisterzone.game.state.GameState;

import io.vavr.Function1;

/**
 * Ported verbatim from JCloisterZone 4.x (com.jcloisterzone.ai.GameStateRanking).
 * No semantic deviation.
 */
public interface GameStateRanking extends Function1<GameState, Double> {


}
