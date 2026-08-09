package com.jcloisterzone.ai;

import com.jcloisterzone.action.*;
import com.jcloisterzone.board.PlacementOption;
import com.jcloisterzone.board.Position;
import com.jcloisterzone.board.pointer.FeaturePointer;
import com.jcloisterzone.board.pointer.MeeplePointer;
import com.jcloisterzone.figure.Follower;
import com.jcloisterzone.figure.neutral.NeutralFigure;
import com.jcloisterzone.game.capability.BridgeCapability.BridgeToken;
import com.jcloisterzone.game.capability.CastleCapability.CastleToken;
import com.jcloisterzone.game.capability.FerriesCapability.FerryToken;
import com.jcloisterzone.game.capability.GoldminesCapability.GoldToken;
import com.jcloisterzone.game.capability.LittleBuildingsCapability.LittleBuilding;
import com.jcloisterzone.io.message.*;

import io.vavr.collection.Vector;

/**
 * NEW FILE — has no 4.x counterpart.
 *
 * WHY IT EXISTS (semantic deviation D3, see AiPlayer):
 * In JCloisterZone 4.x every `PlayerAction<T>` carried a `WsInGameMessage select(T option)` method: the
 * action itself knew how to turn a chosen option into the wire message. JCloisterZone 5.x DELETED
 * `select()` from `PlayerAction` (the JS client now builds messages itself), so the AI port has to
 * reconstruct that mapping. Every branch below is transcribed one-for-one from the corresponding 4.x
 * `select()` body (`JCZ4x/src/main/java/com/jcloisterzone/action/*.java`); nothing here is invented.
 *
 * DEVIATIONS, each unreachable in the locked Base+Farmers scope:
 *   - MeepleAction with `Location.FLYING_MACHINE`: 4.x emitted `DeployFlierMessage`, which does not exist
 *     in 5.x (the flier randomness moved into `DeployMeepleMessage.random`, which the AI has no way to
 *     pick). THROWS.
 *   - TowerPieceAction: 4.x built `new FeaturePointer(pos, Location.TOWER)`; 5.x `FeaturePointer` takes a
 *     feature class and there is no `Location.TOWER`. Rather than guess the 5.x encoding, THROWS.
 *   - FlockAction / CornCircleSelectDeployOrRemoveAction / BazaarSelectBuyOrSellAction: in 5.x these are
 *     `AbstractPlayerAction<Void>` with no option set at all (the option moved into constructor state),
 *     so there is no option to select. THROW.
 *   - BazaarBidAction / BazaarSelectTileAction: threw `UnsupportedOperationException` in 4.x too. THROW.
 *   - ScoreAcrobatsAction: 5.x-only action with no 4.x counterpart; mapped to `ScoreAcrobatsMessage`
 *     by direct analogy (the only message it can produce).
 *   - ConfirmAction: 4.x had a single `Boolean.TRUE` option; 5.x constructs it with `null` options.
 *     Handled specially in {@link #createMessages} so the CommitMessage is still reachable.
 */
public final class MessageFactory {

    private MessageFactory() {
    }

    /**
     * All messages the given action can produce. Replaces
     * `action.getOptions().map(action::select)` from 4.x.
     */
    public static Vector<ReplayableMessage> createMessages(PlayerAction<?> action) {
        if (action instanceof ConfirmAction) {
            // 4.x: ConfirmAction had options = {Boolean.TRUE} and select(_) -> CommitMessage.
            // 5.x: options is null, so reproduce the single option here.
            return Vector.of(new CommitMessage());
        }
        if (action.getOptions() == null) {
            return Vector.empty();
        }
        return action.getOptions().toVector().map(o -> createMessage(action, o));
    }

    @SuppressWarnings({ "rawtypes", "unchecked" })
    public static ReplayableMessage createMessage(PlayerAction action, Object option) {
        // --- transcribed from 4.x TilePlacementAction.select ---
        if (action instanceof TilePlacementAction) {
            TilePlacementAction a = (TilePlacementAction) action;
            PlacementOption tp = (PlacementOption) option;
            return new PlaceTileMessage(a.getTile().getId(), tp.getRotation(), tp.getPosition());
        }
        // --- transcribed from 4.x MeepleAction.select ---
        if (action instanceof MeepleAction) {
            MeepleAction a = (MeepleAction) action;
            FeaturePointer fp = (FeaturePointer) option;
            if ("FLYING_MACHINE".equals(String.valueOf(fp.getLocation()))) {
                throw new UnsupportedOperationException(
                    "FLYING_MACHINE deployment has no 5.x equivalent of 4.x DeployFlierMessage");
            }
            return new DeployMeepleMessage(fp, a.getMeepleIdFor(fp));
        }
        // --- transcribed from 4.x ReturnMeepleAction.select ---
        if (action instanceof ReturnMeepleAction) {
            ReturnMeepleAction a = (ReturnMeepleAction) action;
            return new ReturnMeepleMessage((MeeplePointer) option, a.getSource());
        }
        // --- transcribed from 4.x CaptureFollowerAction.select ---
        if (action instanceof CaptureFollowerAction) {
            return new CaptureFollowerMessage((MeeplePointer) option);
        }
        // --- transcribed from 4.x BridgeAction.select ---
        if (action instanceof BridgeAction) {
            return new PlaceTokenMessage(BridgeToken.BRIDGE, (FeaturePointer) option);
        }
        // --- transcribed from 4.x CastleAction.select ---
        if (action instanceof CastleAction) {
            return new PlaceTokenMessage(CastleToken.CASTLE, (FeaturePointer) option);
        }
        // --- transcribed from 4.x FerriesAction.select ---
        if (action instanceof FerriesAction) {
            return new PlaceTokenMessage(FerryToken.FERRY, (FeaturePointer) option);
        }
        // --- transcribed from 4.x TunnelAction.select ---
        if (action instanceof TunnelAction) {
            TunnelAction a = (TunnelAction) action;
            return new PlaceTokenMessage(a.getToken(), (FeaturePointer) option);
        }
        // --- transcribed from 4.x LittleBuildingAction.select ---
        if (action instanceof LittleBuildingAction) {
            LittleBuildingAction a = (LittleBuildingAction) action;
            return new PlaceTokenMessage((LittleBuilding) option, a.getPosition());
        }
        // --- transcribed from 4.x GoldPieceAction.select ---
        if (action instanceof GoldPieceAction) {
            return new PlaceTokenMessage(GoldToken.GOLD, (Position) option);
        }
        // --- transcribed from 4.x MoveDragonAction.select ---
        if (action instanceof MoveDragonAction) {
            MoveDragonAction a = (MoveDragonAction) action;
            return new MoveNeutralFigureMessage(a.getFigureId(), (Position) option);
        }
        // --- transcribed from 4.x FairyOnTileAction.select ---
        if (action instanceof FairyOnTileAction) {
            FairyOnTileAction a = (FairyOnTileAction) action;
            return new MoveNeutralFigureMessage(a.getFigureId(), (Position) option);
        }
        // --- transcribed from 4.x FairyNextToAction.select ---
        if (action instanceof FairyNextToAction) {
            FairyNextToAction a = (FairyNextToAction) action;
            return new MoveNeutralFigureMessage(a.getFigureId(), (MeeplePointer) option);
        }
        // --- transcribed from 4.x NeutralFigureAction.select ---
        if (action instanceof NeutralFigureAction) {
            NeutralFigureAction a = (NeutralFigureAction) action;
            return new MoveNeutralFigureMessage(a.getFigure().getId(), (FeaturePointer) option);
        }
        // --- transcribed from 4.x RemovMageOrWithAction.select (renamed RemoveMageOrWitchAction in 5.x) ---
        if (action instanceof RemoveMageOrWitchAction) {
            NeutralFigure<FeaturePointer> fig = (NeutralFigure<FeaturePointer>) option;
            return new MoveNeutralFigureMessage(fig.getId(), null);
        }
        // --- transcribed from 4.x SelectPrisonerToExchangeAction.select ---
        if (action instanceof SelectPrisonerToExchangeAction) {
            return new ExchangeFollowerChoiceMessage(((Follower) option).getId());
        }
        // --- 5.x-only, no 4.x counterpart ---
        if (action instanceof ScoreAcrobatsAction) {
            return new ScoreAcrobatsMessage((FeaturePointer) option);
        }
        throw new UnsupportedOperationException(
            "No 5.x message mapping for action " + action.getClass().getName());
    }
}
