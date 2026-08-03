import os

from wingedsheep.carcassonne.objects.connection import Connection
from wingedsheep.carcassonne.objects.farmer_connection import FarmerConnection
from wingedsheep.carcassonne.objects.side import Side
from wingedsheep.carcassonne.objects.tile import Tile
from wingedsheep.carcassonne.objects.farmer_side import FarmerSide

base_tiles = {
    "chapel_with_road": Tile(
        description="chapel_with_road",
        road=[Connection(Side.BOTTOM, Side.CENTER)],
        grass=[Side.LEFT, Side.TOP, Side.RIGHT],
        chapel=True,
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.TRT, FarmerSide.TRR,
                    FarmerSide.BRR, FarmerSide.BRB,
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_A.png")
    ),
    "chapel": Tile(
        description="chapel",
        grass=[Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.TRT, FarmerSide.TRR,
                    FarmerSide.BRR, FarmerSide.BRB,
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            )
        ],
        chapel=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_B.png")
    ),
    "full_city_with_shield": Tile(
        description="full_city_with_shield",
        city=[[Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT]],
        shield=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_C.png")
    ),
    "city_top_straight_road": Tile(
        description="city_top_straight_road",
        road=[Connection(Side.LEFT, Side.RIGHT)],
        city=[[Side.TOP]],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.TRT, FarmerSide.TRR
                ],
                city_sides=[
                    Side.TOP
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRR, FarmerSide.BRB,
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            )
        ],
        grass=[Side.BOTTOM],
        image=os.path.join("base_game", "Base_Game_C2_Tile_D.png")
    ),
    "city_top": Tile(
        description="city_top",
        city=[[Side.TOP]],
        grass=[Side.RIGHT, Side.BOTTOM, Side.LEFT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.TRR,
                    FarmerSide.BRR, FarmerSide.BRB,
                    FarmerSide.BLB, FarmerSide.BLL
                ],
                city_sides=[
                    Side.TOP
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_E.png")
    ),
    "city_top_flowers": Tile(
        description="city_top_flowers",
        city=[[Side.TOP]],
        grass=[Side.RIGHT, Side.BOTTOM, Side.LEFT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.TRR,
                    FarmerSide.BRR, FarmerSide.BRB,
                    FarmerSide.BLB, FarmerSide.BLL
                ],
                city_sides=[
                    Side.TOP
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_E_Garden.png")
    ),
    "city_narrow_shield": Tile(
        description="city_narrow_shield",
        city=[[Side.LEFT, Side.RIGHT]],
        grass=[Side.TOP, Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLT,
                    FarmerSide.TRT
                ],
                city_sides=[
                    Side.LEFT, Side.RIGHT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB,
                    FarmerSide.BLB
                ],
                city_sides=[
                    Side.LEFT, Side.RIGHT
                ]
            )
        ],
        shield=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_F.png")
    ),
    "city_narrow": Tile(
        description="city_narrow",
        city=[[Side.LEFT, Side.RIGHT]],
        grass=[Side.TOP, Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLT,
                    FarmerSide.TRT
                ],
                city_sides=[
                    Side.LEFT, Side.RIGHT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB,
                    FarmerSide.BLB
                ],
                city_sides=[
                    Side.LEFT, Side.RIGHT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_G.png")
    ),
    "city_left_right": Tile(
        description="city_left_right",
        city=[[Side.LEFT], [Side.RIGHT]],
        grass=[Side.TOP, Side.BOTTOM, Side.CENTER],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLT,
                    FarmerSide.TRT,
                    FarmerSide.BRB,
                    FarmerSide.BLB,
                ],
                city_sides=[
                    Side.LEFT,
                    Side.RIGHT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_H.png")
    ),
    "city_top_bottom_flowers": Tile(
        description="city_top_bottom_flowers",
        city=[[Side.TOP], [Side.BOTTOM]],
        grass=[Side.LEFT, Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.TRR,
                    FarmerSide.BRR,
                    FarmerSide.BLL,
                ],
                city_sides=[
                    Side.TOP,
                    Side.BOTTOM
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_H_Garden.png")
    ),
    "city_top_right": Tile(
        description="city_top_right",
        city=[[Side.TOP], [Side.RIGHT]],
        grass=[Side.LEFT, Side.BOTTOM, Side.CENTER],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.BRB,
                    FarmerSide.BLB, FarmerSide.BLL
                ],
                city_sides=[
                    Side.TOP,
                    Side.RIGHT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_I.png")
    ),
    "city_top_left_flowers": Tile(
        description="city_top_left_flowers",
        city=[[Side.TOP], [Side.LEFT]],
        grass=[Side.BOTTOM, Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TRR,
                    FarmerSide.BRR, FarmerSide.BRB,
                    FarmerSide.BLB
                ],
                city_sides=[
                    Side.LEFT,
                    Side.TOP
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_I_Garden.png")
    ),
    "city_top_road_bend_right": Tile(
        description="city_top_road_bend_right",
        city=[[Side.TOP]],
        road=[Connection(Side.BOTTOM, Side.RIGHT)],
        grass=[Side.LEFT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.TRR,
                    FarmerSide.BLB, FarmerSide.BLL
                ],
                city_sides=[
                    Side.TOP
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRR,
                    FarmerSide.BRB
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_J.png")
    ),
    "city_top_road_bend_left": Tile(
        description="city_top_road_bend_left",
        city=[[Side.TOP]],
        road=[Connection(Side.BOTTOM, Side.LEFT)],
        grass=[Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.TRR,
                    FarmerSide.BRB, FarmerSide.BRR
                ],
                city_sides=[
                    Side.TOP
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLL,
                    FarmerSide.BLB
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_K.png")
    ),
    "city_top_crossroads": Tile(
        description="city_top_crossroads",
        city=[[Side.TOP]],
        road=[
            Connection(Side.BOTTOM, Side.CENTER),
            Connection(Side.LEFT, Side.CENTER),
            Connection(Side.RIGHT, Side.CENTER)
        ],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.TRR,
                ],
                city_sides=[
                    Side.TOP
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLL,
                    FarmerSide.BLB
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB,
                    FarmerSide.BRR
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_L.png")
    ),
    "city_diagonal_top_right_shield": Tile(
        description="city_diagonal_top_right_shield",
        city=[[Side.TOP, Side.RIGHT]],
        grass=[Side.LEFT, Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.BLB, FarmerSide.BLL,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.RIGHT
                ]
            )
        ],
        shield=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_M.png")
    ),
    "city_diagonal_top_right_shield_flowers": Tile(
        description="city_diagonal_top_right_shield_flowers",
        city=[[Side.TOP, Side.RIGHT]],
        grass=[Side.LEFT, Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.BLB, FarmerSide.BLL,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.RIGHT
                ]
            )
        ],
        shield=True,
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_M_Garden.png")
    ),
    "city_diagonal_top_right": Tile(
        description="city_diagonal_top_right",
        city=[[Side.TOP, Side.RIGHT]],
        grass=[Side.LEFT, Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.BLB, FarmerSide.BLL,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.RIGHT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_N.png")
    ),
    "city_diagonal_top_right_flowers": Tile(
        description="city_diagonal_top_right_flowers",
        city=[[Side.TOP, Side.RIGHT]],
        grass=[Side.LEFT, Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL,
                    FarmerSide.BLB, FarmerSide.BLL,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.RIGHT
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_N_Garden.png")
    ),
    "city_diagonal_top_left_shield_road": Tile(
        description="city_diagonal_top_left_shield_road",
        road=[Connection(Side.BOTTOM, Side.RIGHT)],
        city=[[Side.TOP, Side.LEFT]],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BLB,
                    FarmerSide.TRR
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRR,
                    FarmerSide.BRB
                ]
            )
        ],
        shield=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_O.png")
    ),
    "city_diagonal_top_left_road": Tile(
        description="city_diagonal_top_left_road",
        road=[Connection(Side.BOTTOM, Side.RIGHT)],
        city=[[Side.TOP, Side.LEFT]],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BLB,
                    FarmerSide.TRR
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRR,
                    FarmerSide.BRB
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_P.png")
    ),
    "city_bottom_grass_shield": Tile(
        description="city_bottom_grass_shield",
        city=[[Side.TOP, Side.LEFT, Side.RIGHT]],
        grass=[Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BLB,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            )
        ],
        shield=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_Q.png")
    ),
    "city_bottom_grass": Tile(
        description="city_bottom_grass",
        city=[[Side.TOP, Side.LEFT, Side.RIGHT]],
        grass=[Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BLB,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_R.png")
    ),
    "city_bottom_grass_flowers": Tile(
        description="city_bottom_grass_flowers",
        city=[[Side.TOP, Side.LEFT, Side.RIGHT]],
        grass=[Side.BOTTOM],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BLB,
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_R_Garden.png")
    ),
    "city_bottom_road_shield": Tile(
        description="city_bottom_road_shield",
        city=[[Side.TOP, Side.LEFT, Side.RIGHT]],
        road=[Connection(Side.BOTTOM, Side.CENTER)],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            )
        ],
        shield=True,
        image=os.path.join("base_game", "Base_Game_C2_Tile_S.png")
    ),
    "city_bottom_road": Tile(
        description="city_bottom_road",
        city=[[Side.TOP, Side.LEFT, Side.RIGHT]],
        road=[Connection(Side.BOTTOM, Side.CENTER)],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB
                ],
                city_sides=[
                    Side.TOP,
                    Side.LEFT,
                    Side.RIGHT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_T.png")
    ),
    "straight_road": Tile(
        description="straight_road",
        road=[Connection(Side.BOTTOM, Side.TOP)],
        grass=[Side.LEFT, Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_RIGHT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TRR, FarmerSide.TRT,
                    FarmerSide.BRR, FarmerSide.BRB
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_U.png")
    ),
    "straight_road_flowers": Tile(
        description="straight_road_flowers",
        road=[Connection(Side.BOTTOM, Side.TOP)],
        grass=[Side.LEFT, Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_RIGHT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TRR, FarmerSide.TRT,
                    FarmerSide.BRR, FarmerSide.BRB
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_U_Garden.png")
    ),
    "bent_road": Tile(
        description="bent_road",
        road=[Connection(Side.LEFT, Side.BOTTOM)],
        grass=[Side.TOP, Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.TRR, FarmerSide.TRT,
                    FarmerSide.BRB, FarmerSide.BRR
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_V.png")
    ),
    "bent_road_flowers": Tile(
        description="bent_road_flowers",
        road=[Connection(Side.LEFT, Side.BOTTOM)],
        grass=[Side.TOP, Side.RIGHT],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT,
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.TRR, FarmerSide.TRT,
                    FarmerSide.BRB, FarmerSide.BRR
                ]
            )
        ],
        flowers=True,
        image=os.path.join("base_game", "Abbot-Base_Game_C2_Tile_V_Garden.png")
    ),
    "three_split_road": Tile(
        description="three_split_road",
        road=[
            Connection(Side.BOTTOM, Side.CENTER),
            Connection(Side.LEFT, Side.CENTER),
            Connection(Side.RIGHT, Side.CENTER)
        ],
        grass=[Side.TOP],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB, FarmerSide.BRR
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT,
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT,
                    FarmerSide.TRR, FarmerSide.TRT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_W.png")
    ),
    "crossroads": Tile(
        description="crossroads",
        road=[
            Connection(Side.BOTTOM, Side.CENTER),
            Connection(Side.LEFT, Side.CENTER),
            Connection(Side.RIGHT, Side.CENTER),
            Connection(Side.TOP, Side.CENTER)
        ],
        farms=[
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_LEFT
                ],
                tile_connections=[
                    FarmerSide.BLB, FarmerSide.BLL
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.BOTTOM_RIGHT
                ],
                tile_connections=[
                    FarmerSide.BRB, FarmerSide.BRR
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_LEFT
                ],
                tile_connections=[
                    FarmerSide.TLL, FarmerSide.TLT
                ]
            ),
            FarmerConnection(
                farmer_positions=[
                    Side.TOP_RIGHT
                ],
                tile_connections=[
                    FarmerSide.TRR, FarmerSide.TRT
                ]
            )
        ],
        image=os.path.join("base_game", "Base_Game_C2_Tile_X.png")
    )
}

base_tile_counts = {
    "chapel_with_road": 2,
    "chapel": 4,
    "full_city_with_shield": 1,
    "city_top_straight_road": 4,
    "city_top": 4,
    "city_top_flowers": 1,
    "city_narrow_shield": 2,
    "city_narrow": 1,
    "city_left_right": 2,
    "city_top_bottom_flowers": 1,
    "city_top_right": 1,
    "city_top_left_flowers": 1,
    "city_top_road_bend_right": 3,
    "city_top_road_bend_left": 3,
    "city_top_crossroads": 3,
    "city_diagonal_top_right_shield": 1,
    "city_diagonal_top_right_shield_flowers": 1,
    "city_diagonal_top_right": 2,
    "city_diagonal_top_right_flowers": 1,
    "city_diagonal_top_left_shield_road": 2,
    "city_diagonal_top_left_road": 3,
    "city_bottom_grass_shield": 1,
    "city_bottom_grass": 2,
    "city_bottom_grass_flowers": 1,
    "city_bottom_road_shield": 2,
    "city_bottom_road": 1,
    "straight_road": 7,
    "straight_road_flowers": 1,
    "bent_road": 8,
    "bent_road_flowers": 1,
    "three_split_road": 4,
    "crossroads": 1
}


# ===========================================================================
# R9 — "a field half-edge may not lie on a city edge"   (F9 remediation)
#
#   *** DEFAULT OFF.  Building this flag adopts nothing. ***
#
# Found 2026-08-03 by the JCloisterZone differential tile oracle
# (measurement/jcz_spike_20260803/SPIKE_REPORT.md, Finding 1; the oracle is now
# tests/test_jcz_tile_oracle.py).  Exactly one of our 32 tile kinds declares a
# farm region containing half-edges that lie on one of its own CITY edges:
#
#     city_top_straight_road (JCZ BA/RCr, x4 in the deck)
#         north field region tile_connections = [TLL, TLT, TRT, TRR]
#         TLT and TRT are the two halves of the NORTH edge — and north is a city.
#         JCZ lists the equivalent of [TLL, TRR] only.  The other 31 kinds agree
#         with JCZ field-for-field, and JCZ's whole base set is clean.
#
# `FarmUtil.find_farm` — and `flat_leaf`, `flat_leaf_cy` and the Rust
# `leaf/decomp.rs`, which all read this same `tile_connections` data — cross a
# tile_connection UNCONDITIONALLY (no grass/city gate anywhere on the
# traversal; the data is supposed to encode that).  So the two surplus entries
# let a field walk straight through a city: two RCr tiles placed city-to-city
# have their under-city field strips merged into ONE farm.  Reproducer +
# control: measurement/jcz_spike_20260803/rcr_merge_probe.py, promoted to
# tests/test_r9_field_on_city_edge.py.
#
# --- what the flag does ----------------------------------------------------
# ON  (CARCASSONNE_FIX_R9=1): every farm region drops the tile_connections that
#     lie on a city edge of the same tile.  Derived by predicate, not by a
#     hand-typed patch, so it cannot transcribe wrong and it stays correct if
#     the deck ever gains another such tile.  Today it removes exactly
#     {TLT, TRT} from one region of one kind — `R9_OVERRIDE` records precisely
#     what changed and is asserted against the JCZ oracle.
# OFF (default): `base_tiles` is the literal data above, untouched, and
#     `scripts/rustport/export_tile_data.py`'s SEMANTIC_DIGEST is unchanged.
#
# --- riders ----------------------------------------------------------------
# * ADOPTION IS NOT MINE TO MAKE.  This is a rules/data change that moves FARM
#   scoring, which is exactly the axis the v2.7/v2.9 leaf's farm caps and
#   curves were tuned against, so `feedback_bug_fix_shifts_optima` applies: if
#   this is ever adopted, RE-SWEEP the leaf's farm caps/weights before trusting
#   any pre-R9 bench number.  See docs/F9_BUILD_SPEC_20260802.md §2.4.
# * The flag is PROCESS-GLOBAL by construction: `base_tiles` is an import-time
#   module global here, and the Rust registry is a `OnceLock` — neither engine
#   has a per-Game tile table.  Set the env var before importing anything.
# * The flag changes NO tile description, count or insertion order, so deck
#   shuffles, action spaces, board reprs and legal masks are bit-identical
#   either way.  Only farm decomposition moves.
# ===========================================================================
R9_ENV_VAR = "CARCASSONNE_FIX_R9"


def _r9_env_on(environ=None) -> bool:
    raw = (os.environ if environ is None else environ).get(R9_ENV_VAR, "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def r9_farm_override(tiles=None) -> dict:
    """`{description: [FarmerConnection, ...]}` for every tile whose farm data
    changes under R9 — computed from the tile's own geometry.

    A *road* edge legitimately carries field on both halves (a road is a line,
    not a band); only a **city** edge carries none.  That is the whole rule.
    Pure function: it does not consult the flag and does not mutate anything.
    """
    tiles = base_tiles if tiles is None else tiles
    override = {}
    for name, tile in tiles.items():
        city_edges = {side for group in (tile.city or []) for side in group}
        if not city_edges:
            continue
        new_farms, changed = [], False
        for fc in (tile.farms or []):
            keep = [fs for fs in fc.tile_connections if fs.get_side() not in city_edges]
            if len(keep) != len(fc.tile_connections):
                changed = True
                new_farms.append(FarmerConnection(
                    farmer_positions=list(fc.farmer_positions),
                    tile_connections=keep,
                    city_sides=list(fc.city_sides),
                ))
            else:
                new_farms.append(fc)
        if changed:
            override[name] = new_farms
    return override


def _r9_apply(tiles: dict, override: dict) -> None:
    """Replace each overridden tile with a fresh, otherwise-identical `Tile`.

    A fresh object rather than an in-place mutation: `Tile` memoises
    `_type_cache` / `_rot_sig_cache` / `_turn_cache` lazily and hands out
    canonical shared references, so mutating farms under a live cache would be
    a correctness trap.  At import time nothing holds a reference yet.
    """
    for name, farms in override.items():
        old = tiles[name]
        tiles[name] = Tile(
            description=old.description, turns=old.turns,
            road=old.road, river=old.river, city=old.city, grass=old.grass,
            farms=farms, shield=old.shield, chapel=old.chapel,
            flowers=old.flowers, inn=old.inn, cathedral=old.cathedral,
            unplayable_sides=old.unplayable_sides, image=old.image,
        )


#: What R9 *would* change, always available regardless of the flag state (the
#: exporter and the parity tests need it in both states).
R9_OVERRIDE = r9_farm_override(base_tiles)

#: Resolved flag state for this process.  Read once, at import.
R9_FIELD_ON_CITY_EDGE_FIX = _r9_env_on()

if R9_FIELD_ON_CITY_EDGE_FIX:
    _r9_apply(base_tiles, R9_OVERRIDE)
