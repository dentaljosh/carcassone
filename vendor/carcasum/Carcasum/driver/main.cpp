/*
	This file is part of Carcasum.

	Carcasum is free software: you can redistribute it and/or modify
	it under the terms of the GNU Affero General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	Carcasum is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU Affero General Public License for more details.

	You should have received a copy of the GNU Affero General Public License
	along with Carcasum.  If not, see <http://www.gnu.org/licenses/>.
*/

// carcasum_driver -- line-JSON stdin/stdout driver. See
// scripts/carcasum_match/PROTOCOL.md in the parent repo for the contract this
// file implements. Do not deviate from that spec without updating it first.

#include "static.h"
#include "core/game.h"
#include "core/board.h"
#include "core/tile.h"
#include "core/player.h"
#include "core/nexttileprovider.h"
#include "jcz/tilefactory.h"
#include "jcz/jczplayer.h"
#include "player/randomplayer.h"
#include "player/montecarloplayer.h"
#include "player/montecarloplayer2.h"
#include "player/montecarloplayeruct.h"
#include "player/mctsplayer.h"
#include "player/simpleplayer3.h"
#include "player/utilities.h"
#include "player/playouts.h"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonValue>
#include <QByteArray>
#include <QString>
#include <QStringList>

#include <boost/chrono.hpp>

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
#include <string>
#include <vector>

// ---------------------------------------------------------------------------
// stdout/stdin line protocol helpers.
//
// stdout carries ONLY protocol lines (PROTOCOL.md section 1). Everything else
// -- diagnostics, the wall-vs-thread-cpu smoke numbers below -- goes to
// stderr. Qt's default qDebug/qWarning handler already writes to stderr, so
// as long as this file itself never touches std::cout except through
// emitLine(), stdout purity holds by construction.
// ---------------------------------------------------------------------------

static void emitLine(QJsonObject const & obj)
{
	QJsonDocument doc(obj);
	QByteArray bytes = doc.toJson(QJsonDocument::Compact);
	std::cout.write(bytes.constData(), bytes.size());
	std::cout.put('\n');
	std::cout.flush();
}

// Emits {"t":"fault", ...} and terminates the process non-zero, per
// PROTOCOL.md section 3.2(f)/5. Never returns.
[[noreturn]] static void faultExit(QString const & why, QJsonObject detail = QJsonObject())
{
	QJsonObject obj;
	obj["t"] = QStringLiteral("fault");
	obj["why"] = why;
	obj["detail"] = detail;
	emitLine(obj);
	std::exit(1);
}

// Blocks on one stdin line. EOF or an explicit {"t":"quit"} both mean "exit 0
// now", per PROTOCOL.md section 3.3 -- this is the ONLY place that decides
// that, so every blocking read in this file (the new_game handshake, every
// req_tile/req_meeple response, and the post-game_over wait) goes through it.
// Malformed JSON is a fault, not a silent skip.
static QJsonObject readLineOrExit()
{
	std::string line;
	if (!std::getline(std::cin, line))
		std::exit(0);

	QJsonParseError err;
	QJsonDocument doc = QJsonDocument::fromJson(QByteArray::fromStdString(line), &err);
	if (err.error != QJsonParseError::NoError || !doc.isObject())
		faultExit(QStringLiteral("invalid_move"), QJsonObject{
		              {"reason", QStringLiteral("malformed json line on stdin")},
		              {"raw", QString::fromStdString(line)},
		              {"parse_error", err.errorString()}});

	QJsonObject obj = doc.object();
	if (obj.value(QStringLiteral("t")).toString() == QStringLiteral("quit"))
		std::exit(0);
	return obj;
}

// ---------------------------------------------------------------------------
// Tile structure introspection, shared between --dump-tiles and req_meeple's
// board-absolute node labels (PROTOCOL.md section 2 and section 4).
//
// The SAME function serves both because Tile::getEdge()/getEdgeNodeAndIndex()
// (no-orientation overloads) already read through the tile's own
// `orientation` member (core/tile.cpp:402-410, 557-575). For a tile fresh out
// of TileFactory::createPack(), orientation == Tile::left (0), so this
// produces tile-local/base-orientation labels; for a tile already placed on
// the board (Board::addTile sets tile->orientation = move.orientation before
// Game::step() asks for the meeple move -- core/board.cpp:63), the exact same
// call produces board-absolute labels. No manual N->E->S->W rotation of
// label strings is needed or performed.
// ---------------------------------------------------------------------------

static QString terrainLetter(TerrainType t)
{
	switch (t)
	{
		case Field:    return QStringLiteral("F");
		case City:     return QStringLiteral("C");
		case Road:     return QStringLiteral("R");
		case Cloister: return QStringLiteral("Y"); // never a base-tile edge terrain; defensive only
		case None:     return QStringLiteral("N"); // never expected on a real base tile; defensive only
	}
	return QStringLiteral("?");
}

static QString terrainName(TerrainType t)
{
	switch (t)
	{
		case Field:    return QStringLiteral("field");
		case City:     return QStringLiteral("city");
		case Road:     return QStringLiteral("road");
		case Cloister: return QStringLiteral("cloister");
		case None:     return QStringLiteral("none");
	}
	return QStringLiteral("unknown");
}

// Per node index (0..getNodeCount()-1): the JCZ-vocabulary label set derived
// from which (side, slot) pairs address it (PROTOCOL.md section 4):
//   * Field edge  -> slot 1 only, but labelled BOTH {side}L and {side}R
//     (readXMLTile only ever populates slot 1 for a Field edge -- jcz/tilefactory.cpp:367-369 --
//     even though the field spans the whole edge; both halves address the same node).
//   * City edge   -> slot 1 only, labelled plain {side} (no L/R -- the R9 convention).
//   * Road edge   -> slot 0 = {side}R (field), slot 1 = plain {side} (the road),
//     slot 2 = {side}L (field) -- jcz/tilefactory.cpp:373-376.
//   * Cloister    -> its own node, labelled "CLOISTER", independent of any side.
static std::vector<std::vector<QString>> computeNodeLabels(Tile const * tile)
{
	std::vector<std::vector<QString>> labels(tile->getNodeCount());

	struct SideInfo { Tile::Side side; char const * letter; };
	static SideInfo const sides[4] = {
	    { Tile::left,  "W" },
	    { Tile::up,    "N" },
	    { Tile::right, "E" },
	    { Tile::down,  "S" },
	};

	for (SideInfo const & si : sides)
	{
		TerrainType e = tile->getEdge(si.side);
		QString const letter = QString::fromLatin1(si.letter);
		uchar idx;
		switch (e)
		{
			case Field:
				tile->getEdgeNodeAndIndex(si.side, 1, idx);
				labels[idx].push_back(letter + QStringLiteral("L"));
				labels[idx].push_back(letter + QStringLiteral("R"));
				break;
			case City:
				tile->getEdgeNodeAndIndex(si.side, 1, idx);
				labels[idx].push_back(letter);
				break;
			case Road:
			{
				uchar idxR, idxF, idxL;
				tile->getEdgeNodeAndIndex(si.side, 0, idxR);
				labels[idxR].push_back(letter + QStringLiteral("R"));
				tile->getEdgeNodeAndIndex(si.side, 1, idxF);
				labels[idxF].push_back(letter);
				tile->getEdgeNodeAndIndex(si.side, 2, idxL);
				labels[idxL].push_back(letter + QStringLiteral("L"));
				break;
			}
			case Cloister:
			case None:
				break;
		}
	}

	Node const * cloisterNode = tile->getCloisterNode();
	if (cloisterNode != nullptr)
	{
		for (uchar i = 0, n = tile->getNodeCount(); i < n; ++i)
		{
			if (tile->getNode(i) == cloisterNode)
			{
				labels[i].push_back(QStringLiteral("CLOISTER"));
				break;
			}
		}
	}

	return labels;
}

static QJsonArray labelsToJson(std::vector<QString> const & labels)
{
	QJsonArray arr;
	for (QString const & l : labels)
		arr.append(l);
	return arr;
}

// ---------------------------------------------------------------------------
// ForcedTileProvider -- PROTOCOL.md section 3.1. No RNG fallback, ever: a
// cursor overrun or an exhausted tile type is a fault, not a random draw.
//
// Game::getTileIndexByType() asserts internally
// (Q_ASSERT(tiles[index]->tileType == tileType && ...), core/game.h:224), but
// this driver is built in release mode where Q_ASSERT compiles to nothing --
// a desync would otherwise silently hand back a garbage index instead of
// tripping the assert. So this class checks the remaining per-type tile
// count itself, unconditionally, before ever calling getTileIndexByType().
// ---------------------------------------------------------------------------

class ForcedTileProvider : public NextTileProvider
{
private:
	std::vector<int> deck;
	size_t cursor = 0;

public:
	explicit ForcedTileProvider(std::vector<int> d) : deck(std::move(d)) {}

	virtual int nextTile(Game const * game) override
	{
		if (cursor >= deck.size())
			faultExit(QStringLiteral("deck_desync"), QJsonObject{
			              {"reason", QStringLiteral("forced deck exhausted")},
			              {"cursor", (qint64)cursor},
			              {"deck_len", (qint64)deck.size()}});

		int const type = deck[cursor];
		TileCountType const & counts = game->getTileCounts();
		if (type < 0 || (size_t)type >= (size_t)counts.size() || counts[type] <= 0)
			faultExit(QStringLiteral("deck_desync"), QJsonObject{
			              {"reason", QStringLiteral("no tile of the requested type remains")},
			              {"tile_type", type},
			              {"cursor", (qint64)cursor}});

		++cursor;
		return game->getTileIndexByType(type);
	}
};

// ---------------------------------------------------------------------------
// ExternalPlayer -- PROTOCOL.md sections 3.2(a)/(b). Blocks on stdin for
// every move; validates the response against the offered set itself (an
// out-of-range/unoffered move is a fault, never silently clamped or retried
// -- PROTOCOL.md section 5).
//
// clone() FINDING: Player::clone() is virtual-pure on the base class, so
// ExternalPlayer must implement it to be concrete, but it is never
// legitimately callable in this driver's own control flow. Player::clone()
// is called from exactly two places in the whole vendored tree --
// core/main.cpp and tournament/main.cpp -- both harnesses that clone the
// full player roster ONCE per worker thread before a batch of games, for
// parallel self-play. Carcasum's MCTS/MonteCarlo search (player/*.tpp) never
// calls Player::clone(): its rollouts run against its OWN simGame and its OWN
// playout policy (Playouts::RandomPlayout etc.), not against the actual
// registered Player objects, so the opponent's search never needs (and never
// asks for) a copy of the external seat. This driver builds exactly one Game
// with two concrete Player objects and never spawns worker-thread clones, so
// ExternalPlayer::clone() is dead code on every real path -- but a clone that
// DID get called and tried to read from the same shared stdin as the
// original would race/deadlock the match. So instead of returning a broken
// clone, it aborts loudly.
// ---------------------------------------------------------------------------

class ExternalPlayer : public Player
{
private:
	Game const * game_ = nullptr;

public:
	ExternalPlayer() = default;

	virtual void newGame(int /*player*/, Game const * game) override { game_ = game; }
	virtual void playerMoved(int, Tile const *, MoveHistoryEntry const &) override {}
	virtual void undoneMove(MoveHistoryEntry const &) override {}
	virtual void endGame() override {}
	virtual QString getTypeName() const override { return QStringLiteral("external"); }

	virtual Player * clone() const override
	{
		std::cerr << "FATAL: ExternalPlayer::clone() was invoked. This driver never expects the "
		             "external seat to be cloned -- see the clone() finding in driver/main.cpp. "
		             "A clone sharing this process's stdin would deadlock the match; aborting "
		             "instead." << std::endl;
		std::abort();
	}

	virtual TileMove getTileMove(int player, Tile const * tile, MoveHistoryEntry const & /*move*/, TileMovesType const & placements) override
	{
		int const ply = game_ != nullptr ? (int)game_->getMoveHistory().size() : -1;

		QJsonObject req;
		req["t"] = QStringLiteral("req_tile");
		req["ply"] = ply;
		req["player"] = player;
		req["tile_type"] = (int)tile->tileType;
		QJsonArray placementsArr;
		for (TileMove const & p : placements)
			placementsArr.append(QJsonArray{ (int)p.x, (int)p.y, (int)p.orientation });
		req["placements"] = placementsArr;
		emitLine(req);

		QJsonObject const resp = readLineOrExit();
		if (resp.value(QStringLiteral("t")).toString() != QStringLiteral("tile"))
			faultExit(QStringLiteral("invalid_move"), QJsonObject{
			              {"reason", QStringLiteral("expected a 'tile' response to req_tile")},
			              {"got", resp}});

		int const oRaw = resp.value(QStringLiteral("o")).toInt(-1);
		if (!resp.contains(QStringLiteral("x")) || !resp.contains(QStringLiteral("y")) || oRaw < 0 || oRaw > 3)
			faultExit(QStringLiteral("invalid_move"), QJsonObject{
			              {"reason", QStringLiteral("malformed tile response (need x, y, o in 0..3)")},
			              {"got", resp}});

		uint const x = (uint)resp.value(QStringLiteral("x")).toInt(-1);
		uint const y = (uint)resp.value(QStringLiteral("y")).toInt(-1);
		TileMove const candidate(x, y, (Tile::Side)oRaw);

		if (std::find(placements.cbegin(), placements.cend(), candidate) == placements.cend())
			faultExit(QStringLiteral("invalid_move"), QJsonObject{
			              {"reason", QStringLiteral("tile move not among the offered placements")},
			              {"x", (int)x}, {"y", (int)y}, {"o", oRaw}});

		return candidate;
	}

	virtual MeepleMove getMeepleMove(int player, Tile const * tile, MoveHistoryEntry const & move, MeepleMovesType const & possible) override
	{
		int const ply = game_ != nullptr ? (int)game_->getMoveHistory().size() : -1;
		std::vector<std::vector<QString>> const labelSets = computeNodeLabels(tile);

		QJsonObject req;
		req["t"] = QStringLiteral("req_meeple");
		req["ply"] = ply;
		req["player"] = player;
		req["tile_type"] = (int)tile->tileType;
		req["placed"] = QJsonArray{ (int)move.move.tileMove.x, (int)move.move.tileMove.y, (int)move.move.tileMove.orientation };

		QJsonArray nodesArr;
		for (MeepleMove const & mm : possible)
		{
			if (mm.isNull())
				continue;
			uchar const idx = mm.nodeIndex;
			QJsonObject no;
			no["i"] = (int)idx;
			no["terrain"] = terrainName(tile->getNode(idx)->getTerrain());
			no["labels"] = labelsToJson(labelSets[idx]);
			nodesArr.append(no);
		}
		req["nodes"] = nodesArr;
		emitLine(req);

		QJsonObject const resp = readLineOrExit();
		if (resp.value(QStringLiteral("t")).toString() != QStringLiteral("meeple"))
			faultExit(QStringLiteral("invalid_move"), QJsonObject{
			              {"reason", QStringLiteral("expected a 'meeple' response to req_meeple")},
			              {"got", resp}});

		MeepleMove candidate; // null ("no meeple") by default
		QJsonValue const iVal = resp.value(QStringLiteral("i"));
		if (!iVal.isNull())
		{
			int const idx = iVal.toInt(-1);
			if (idx < 0 || idx > 255)
				faultExit(QStringLiteral("invalid_move"), QJsonObject{
				              {"reason", QStringLiteral("meeple node index out of range")},
				              {"i", idx}});
			candidate = MeepleMove((uchar)idx);
		}

		if (std::find(possible.cbegin(), possible.cend(), candidate) == possible.cend())
			faultExit(QStringLiteral("invalid_move"), QJsonObject{
			              {"reason", QStringLiteral("meeple move not among the offered set")},
			              {"i", candidate.isNull() ? QJsonValue() : QJsonValue((int)candidate.nodeIndex)}});

		return candidate;
	}
};

// ---------------------------------------------------------------------------
// Opponent construction -- PROTOCOL.md section 3.1's "opponent" object.
// ---------------------------------------------------------------------------

static Player * buildOpponent(QJsonObject const & opp, jcz::TileFactory * tileFactory)
{
	QString const kind = opp.value(QStringLiteral("kind")).toString();

	bool const playoutsIsSet = opp.contains(QStringLiteral("playouts")) && !opp.value(QStringLiteral("playouts")).isNull();
	bool const budgetIsSet = opp.contains(QStringLiteral("budget_ms")) && !opp.value(QStringLiteral("budget_ms")).isNull();

	uint m = TIMEOUT;
	bool mIsTimeout = true;
	if (playoutsIsSet)
	{
		m = (uint)opp.value(QStringLiteral("playouts")).toInt();
		mIsTimeout = false;
	}
	else if (budgetIsSet)
	{
		m = (uint)opp.value(QStringLiteral("budget_ms")).toInt();
		mIsTimeout = true;
	}

	if (kind == QStringLiteral("mcts"))
	{
		QString const utility = opp.contains(QStringLiteral("utility")) ? opp.value(QStringLiteral("utility")).toString() : QStringLiteral("portion");
		QString const playout = opp.contains(QStringLiteral("playout")) ? opp.value(QStringLiteral("playout")).toString() : QStringLiteral("random");
		if (utility != QStringLiteral("portion") || playout != QStringLiteral("random"))
			faultExit(QStringLiteral("internal"), QJsonObject{
			              {"reason", QStringLiteral("only utility=portion / playout=random are wired for kind=mcts "
			                                         "(PROTOCOL.md's pre-registered opponent); other combinations "
			                                         "would need additional template instantiations")},
			              {"utility", utility}, {"playout", playout}});

		qreal const cp = opp.contains(QStringLiteral("cp")) ? opp.value(QStringLiteral("cp")).toDouble() : 0.5;
		bool const reuseTree = opp.value(QStringLiteral("reuse_tree")).toBool(false);
		bool const nodePriors = opp.value(QStringLiteral("node_priors")).toBool(false);
		bool const progressiveWidening = opp.value(QStringLiteral("progressive_widening")).toBool(false);
		bool const progressiveBias = opp.value(QStringLiteral("progressive_bias")).toBool(false);

		return new MCTSPlayer<Utilities::PortionUtility, Playouts::RandomPlayout>(
		            tileFactory, reuseTree, m, mIsTimeout, cp, nodePriors, progressiveWidening, progressiveBias);
	}
	else if (kind == QStringLiteral("montecarlo"))
	{
		return new MonteCarloPlayer<>(tileFactory, (int)m, mIsTimeout);
	}
	else if (kind == QStringLiteral("montecarlo2"))
	{
		return new MonteCarloPlayer2<>(tileFactory, (int)m, mIsTimeout);
	}
	else if (kind == QStringLiteral("uct"))
	{
		return new MonteCarloPlayerUCT<>(tileFactory, (int)m, mIsTimeout);
	}
	else if (kind == QStringLiteral("simple3"))
	{
		return new SimplePlayer3();
	}
	else if (kind == QStringLiteral("jcz"))
	{
		return new jcz::JCZPlayer(tileFactory);
	}
	else if (kind == QStringLiteral("random"))
	{
		return new RandomPlayer();
	}

	faultExit(QStringLiteral("internal"), QJsonObject{
	              {"reason", QStringLiteral("unknown opponent.kind")},
	              {"kind", kind}});
}

// ---------------------------------------------------------------------------
// --dump-tiles mode -- PROTOCOL.md section 4. No Game is played; a bare Game
// object is still required because Node's constructor reads g->getPlayerCount()
// (core/tile.cpp:27-35) -- an un-started Game (never given players) answers 0,
// which is a legal (zero-length) allocation, so this is safe without ever
// calling Game::newGame().
// ---------------------------------------------------------------------------

namespace {
class NullNextTileProvider : public NextTileProvider
{
public:
	virtual int nextTile(Game const *) override { return 0; }
};
}

static void dumpTilesMode(jcz::TileFactory * tileFactory)
{
	NullNextTileProvider nullNtp;
	Game dummyGame(&nullNtp);

	QList<Tile *> pack = tileFactory->createPack(Tile::BaseGame, &dummyGame);
	int const positionedType = pack.isEmpty() ? -1 : pack.first()->tileType;

	std::map<int, Tile *> representative;
	std::map<int, int> counts;
	for (Tile * t : pack)
	{
		++counts[t->tileType];
		if (representative.find(t->tileType) == representative.end())
			representative[t->tileType] = t;
	}

	static Tile::Side const edgeOrder[4] = { Tile::left, Tile::up, Tile::right, Tile::down };

	QJsonArray tilesArr;
	for (auto const & kv : representative)
	{
		int const type = kv.first;
		Tile const * t = kv.second;

		QJsonObject to;
		to["tile_type"] = type;
		to["id"] = tileFactory->getTileIdentifier(Tile::BaseGame, (TileTypeType)type);
		to["deck_count"] = counts[type];

		QJsonArray edgesArr;
		for (Tile::Side s : edgeOrder)
			edgesArr.append(terrainLetter(t->getEdge(s)));
		to["edges"] = edgesArr;

		to["has_position"] = (type == positionedType);

		std::vector<std::vector<QString>> const labelSets = computeNodeLabels(t);
		QJsonArray nodesArr;
		for (uchar i = 0, n = t->getNodeCount(); i < n; ++i)
		{
			QJsonObject no;
			no["i"] = (int)i;
			Node const * node = t->getNode(i);
			no["terrain"] = terrainName(node->getTerrain());
			no["labels"] = labelsToJson(labelSets[i]);
			int pennant = 0;
			if (CityNode const * cn = dynamic_cast<CityNode const *>(node))
				pennant = cn->getBonus();
			no["pennant"] = pennant;
			nodesArr.append(no);
		}
		to["nodes"] = nodesArr;

		tilesArr.append(to);
	}

	QJsonObject out;
	out["t"] = QStringLiteral("tiles");
	out["revision"] = QStringLiteral(APP_REVISION_STR);
	out["count"] = (int)representative.size();
	out["tiles"] = tilesArr;
	emitLine(out);

	qDeleteAll(pack);
}

// ---------------------------------------------------------------------------
// play mode -- PROTOCOL.md section 3.
// ---------------------------------------------------------------------------

static QJsonObject scoreDetailToJson(Game const & game)
{
	QJsonObject detail;
	QJsonArray fieldArr, cityArr, roadArr, cloisterArr;
	for (uint i = 0; i < game.getPlayerCount(); ++i)
	{
		fieldArr.append(game.getScoreDetail(Field, (int)i));
		cityArr.append(game.getScoreDetail(City, (int)i));
		roadArr.append(game.getScoreDetail(Road, (int)i));
		cloisterArr.append(game.getScoreDetail(Cloister, (int)i));
	}
	detail["field"] = fieldArr;
	detail["city"] = cityArr;
	detail["road"] = roadArr;
	detail["cloister"] = cloisterArr;
	return detail;
}

static QJsonArray scoresToJson(Game const & game)
{
	QJsonArray arr;
	for (uint i = 0; i < game.getPlayerCount(); ++i)
		arr.append(game.getPlayerScore((int)i));
	return arr;
}

static void playMode(jcz::TileFactory * tileFactory)
{
	QJsonObject const newGameMsg = readLineOrExit();
	if (newGameMsg.value(QStringLiteral("t")).toString() != QStringLiteral("new_game"))
		faultExit(QStringLiteral("internal"), QJsonObject{
		              {"reason", QStringLiteral("expected 'new_game' as the first line")},
		              {"got", newGameMsg}});

	QJsonArray const deckArr = newGameMsg.value(QStringLiteral("deck")).toArray();
	std::vector<int> deck;
	deck.reserve((size_t)deckArr.size());
	for (QJsonValue const & v : deckArr)
		deck.push_back(v.toInt());

	if (deck.size() != 71)
		faultExit(QStringLiteral("internal"), QJsonObject{
		              {"reason", QStringLiteral("'deck' must have exactly 71 entries (the start tile is implicit)")},
		              {"got_len", (int)deck.size()}});

	int const externalSeat = newGameMsg.value(QStringLiteral("external_seat")).toInt(-1);
	if (externalSeat != 0 && externalSeat != 1)
		faultExit(QStringLiteral("internal"), QJsonObject{
		              {"reason", QStringLiteral("'external_seat' must be 0 or 1")},
		              {"got", externalSeat}});

	QJsonObject const opponent = newGameMsg.value(QStringLiteral("opponent")).toObject();
	// newGameMsg["seed"] is intentionally NOT wired -- see the seeding finding
	// in the task report. Neither DefaultRandom nor RandomTable (core/random.h)
	// expose a runtime seed setter; the only lever is the compile-time
	// RANDOM_SEED macro, which is process-global and fixed at build time, not
	// settable per new_game message.

	ForcedTileProvider * ftp = new ForcedTileProvider(deck);
	Game game(ftp);

	std::vector<Player *> seats(2, nullptr);
	seats[externalSeat] = new ExternalPlayer();
	seats[1 - externalSeat] = buildOpponent(opponent, tileFactory);

	game.addPlayer(seats[0]);
	game.addPlayer(seats[1]);

	game.newGame(Tile::BaseGame, tileFactory);

	// NOTE (protocol correction -- see the task report): PROTOCOL.md's coordinate
	// table claims size=72/offset=36/start=(36,36). That is wrong. Board::Board()
	// stores `size = s*2 + 1` where `s` is the ctor argument (core/board.cpp:20-22),
	// and Game::newGame() passes tiles.size()==72 as that argument -- so the REAL
	// internal board is 145x145, getOffset()==72, and the start tile is placed at
	// (72,72) (Board::setStartTile uses `offset = size/2`, core/board.cpp:40-49).
	// This driver reports the measured values, not the documented ones.
	int const offset = game.getBoard()->getOffset();
	Tile const * startTile = game.getBoard()->getTile((uint)offset, (uint)offset);

	QJsonObject ready;
	ready["t"] = QStringLiteral("ready");
	ready["start_tile_type"] = startTile != nullptr ? (int)startTile->tileType : -1;
	ready["start_xy"] = QJsonArray{ offset, offset };
	ready["board_size"] = (int)game.getBoard()->getInternalSize();
	ready["deck_len"] = (int)deck.size();
	ready["players"] = QJsonArray{ seats[0]->getTypeName(), seats[1]->getTypeName() };
	ready["revision"] = QStringLiteral(APP_REVISION_STR);
	ready["patches"] = QJsonArray{
	    QStringLiteral("R1_tiny_city_modern"),
	    QStringLiteral("B1_revision_pin"), QStringLiteral("B2_qdatastream_include"),
	    QStringLiteral("B3_cmath_include"), QStringLiteral("B4_assert_guard"),
	    QStringLiteral("B5_count_playouts"), QStringLiteral("B6_game_score_detail_accessor"),
	    QStringLiteral("B7_citynode_bonus_accessor"), QStringLiteral("B8_driver_target"),
	};
	emitLine(ready);

	size_t prevHistSize = game.getMoveHistory().size();
	QElapsedTimer wallTimer;

	for (;;)
	{
		int const playerBefore = game.getNextPlayer();
		Player * actorBefore = (playerBefore >= 0 && (uint)playerBefore < seats.size()) ? seats[(size_t)playerBefore] : nullptr;
		int const playoutsBefore = actorBefore != nullptr ? actorBefore->playouts : 0;

		boost::chrono::thread_clock::time_point const cpuStart = boost::chrono::thread_clock::now();
		wallTimer.start();
		bool const cont = game.step();
		qint64 const wallNs = wallTimer.nsecsElapsed();
		boost::chrono::nanoseconds const cpuNs = boost::chrono::thread_clock::now() - cpuStart;

		size_t const newHistSize = game.getMoveHistory().size();
		if (newHistSize == prevHistSize)
			faultExit(QStringLiteral("internal"), QJsonObject{
			              {"reason", QStringLiteral("Game::step() returned without recording a move "
			                                         "(a registered player returned an invalid move "
			                                         "10 times in a row)")}});

		MoveHistoryEntry const & entry = game.getMoveHistory().back();
		int const ply = (int)newHistSize - 1;
		prevHistSize = newHistSize;

		int const discardedTotal = (int)game.getDiscardedTiles().size();
		int const tilesLeft = game.getTileCount();

		if (entry.move.tileMove.isNull())
		{
			QJsonObject ev;
			ev["t"] = QStringLiteral("ev_discard");
			ev["ply"] = ply;
			ev["player"] = playerBefore;
			ev["tile_type"] = (int)entry.tileType;
			ev["discarded"] = discardedTotal;
			ev["tiles_left"] = tilesLeft;
			emitLine(ev);
		}
		else
		{
			int const playoutsAfter = actorBefore != nullptr ? actorBefore->playouts : 0;

			// Diagnostic only, stderr -- compares driver-measured wall time to
			// driver-measured same-thread CPU time for this ply. Not part of the
			// wire protocol (PROTOCOL.md's ev_move only specifies "ms"); see the
			// wall-vs-thread-cpu finding in the task report.
			double const wallMs = (double)wallNs / 1.0e6;
			double const cpuMs = (double)boost::chrono::duration_cast<boost::chrono::microseconds>(cpuNs).count() / 1000.0;
			std::cerr << "[timing] ply=" << ply << " player=" << playerBefore
			          << " wall_ms=" << wallMs << " thread_cpu_ms=" << cpuMs << std::endl;

			QJsonObject ev;
			ev["t"] = QStringLiteral("ev_move");
			ev["ply"] = ply;
			ev["player"] = playerBefore;
			ev["tile_type"] = (int)entry.tileType;
			ev["x"] = (int)entry.move.tileMove.x;
			ev["y"] = (int)entry.move.tileMove.y;
			ev["o"] = (int)entry.move.tileMove.orientation;
			ev["meeple"] = entry.move.meepleMove.isNull() ? QJsonValue() : QJsonValue((int)entry.move.meepleMove.nodeIndex);
			ev["scores"] = scoresToJson(game);
			ev["score_detail"] = scoreDetailToJson(game);

			QJsonArray meeplesArr;
			for (uint i = 0; i < game.getPlayerCount(); ++i)
				meeplesArr.append(game.getPlayerMeeples((int)i));
			ev["meeples_left"] = meeplesArr;

			ev["discarded"] = discardedTotal;
			ev["tiles_left"] = tilesLeft;
			ev["ms"] = wallMs;
			ev["playouts"] = playoutsAfter - playoutsBefore;
			emitLine(ev);
		}

		if (!cont)
			break;
	}

	QJsonObject over;
	over["t"] = QStringLiteral("game_over");
	over["scores"] = scoresToJson(game);
	over["score_detail"] = scoreDetailToJson(game);
	over["plies"] = (int)game.getMoveHistory().size();
	over["discarded"] = (int)game.getDiscardedTiles().size();

	QJsonArray histArr;
	for (MoveHistoryEntry const & e : game.getMoveHistory())
	{
		QJsonObject ho;
		ho["tile_index"] = e.tileIndex;
		ho["tile_type"] = (int)e.tileType;
		ho["x"] = (int)e.move.tileMove.x;
		ho["y"] = (int)e.move.tileMove.y;
		ho["o"] = (int)e.move.tileMove.orientation;
		ho["meeple"] = e.move.meepleMove.isNull() ? QJsonValue() : QJsonValue((int)e.move.meepleMove.nodeIndex);
		histArr.append(ho);
	}
	over["history"] = histArr;
	emitLine(over);

	// PROTOCOL.md section 3.3: wait for the explicit {"t":"quit"} or EOF
	// shutdown signal rather than exiting out from under Python. Any other
	// well-formed line here is simply not part of this session and is ignored.
	for (;;)
		readLineOrExit();
}

int main(int argc, char * argv[])
{
	QCoreApplication app(argc, argv);
	QStringList const args = app.arguments();

	jcz::TileFactory tileFactory(false);

	if (args.contains(QStringLiteral("--dump-tiles")))
	{
		dumpTilesMode(&tileFactory);
		return 0;
	}

	playMode(&tileFactory);
	return 0;
}
