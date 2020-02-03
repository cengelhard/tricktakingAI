

from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)
from deckView import deck52, Card, suit_keys
import random as rand


from heartsView import GameState, HeartsPlayer, PlayerVec
from heartsModel import HeartsGame
from heartsController import (ControlledGame, 
							  random_controller, 
							  random_legal_controller,
							  hyper_smart_controller,
							  input_controller)
from learnController import sklearn_controller_raw

from sklearn.neural_network import MLPRegressor
from sklearn.linear_model   import LinearRegression
from sklearn.ensemble       import RandomForestRegressor
from sklearn.ensemble       import GradientBoostingRegressor

from sklearn.metrics import mean_squared_error as mse



def play_with_stupid(num_humans=1, game=HeartsGame()):
	game_state = ControlledGame(game, [random_controller(i) if i>num_humans-1 else input_controller(i) for i in range(4)])
	print([p.total_points() for p in game_state.players] if game_state else "game over.")

def test_bug():
	test_bug_hands = [pset(filter(lambda card: card.suit == suit, deck52)) for suit in suit_keys]
	test_bug_state = GameState(trick_leader = 0,
							   players=PlayerVec.create(
									[HeartsPlayer(played=v(),
												  won = v(),
												  prev_player = None,
												  penalty = 0,
												  hand=test_hand) 
										for test_hand in test_bug_hands]))
	return play_with_stupid(1, HeartsGame(test_bug_state))

controller_cast = {
	'Taz': random_controller,
	'Deedee' : random_legal_controller,
	'Dexter':  hyper_smart_controller(), 

}

def c_from_name(name):
	c = controller_cast.get(name)
	return c if c else input_controller

def cs_from_names(names):
	return [c_from_name(name)(i) for i,name in enumerate(names)]

def game_from_cast(names, game=HeartsGame()):
	return ControlledGame(game, cs_from_names(names))

def play_from_cast(names, game=HeartsGame(), num_games=1):
	total_points = [0,0,0,0]
	for g_ind in range(num_games):
		game_state = game_from_cast(names, game)
		for i in range(4):
			total_points[i] += game_state.players[i].total_points()
		print(f"game {g_ind}: {[p.total_points() for p in game_state.players]}")
	print("final scores:")
	for i in range(4):
		print(f"{names[i]}: {total_points[i]}")



def iterate_from_controllers(controllers, iterations):
	scores = [0,0,0,0]
	for _ in range(iterations):
		game_state = ControlledGame(HeartsGame(),controllers)
		for i in range(4):
			scores[i] += game_state.players[i].total_points()
	s = sum(scores)
	return ([score/s for score in scores])

def iterate_from_cast(names, iterations=100):
	return iterate_from_controllers(cs_from_names(names), iterations)


def find_best_Dexter(iterations=10, innerations=30):
	mid = .50
	delta = .25
	for _ in range(iterations):
		low, high = mid-delta, mid+delta
		scores = iterate_from_controllers([hyper_smart_controller(losing_index=low)(0),
										   hyper_smart_controller(losing_index=mid)(1),
									       hyper_smart_controller(losing_index=high)(2),
									       random_legal_controller(3)], innerations)
		print(f"{low} - {mid} - {high}")
		print(scores)
		nextmid = [low, mid, high, mid]

		delta /= 2
		mid = nextmid[scores.index(min(scores))]

			
def Krang():
	controller_cast['Krang'] = sklearn_controller_raw(MLPRegressor(hidden_layer_sizes=(400,40,4), max_iter=1000))

def Walter():
	controller_cast['Walter'] = sklearn_controller_raw(LinearRegression())

def Galadriel():
	controller_cast['Galadriel'] = sklearn_controller_raw(RandomForestRegressor(max_features=100, n_estimators=100))

def Peppy():
	controller_cast['Peppy'] = sklearn_controller_raw(GradientBoostingRegressor(n_estimators=200))

def learn_all():
	 Krang()
	 Walter()
	 Galadriel()
	 Peppy()

'''
TODO:
   + improve printing:
      + sort hand
      +- highlight playable cards
      + show intermediate plays
      + show winner of trick.
   + figure out how continuations are passed.
     + write lookahead AI.
   + proper passing and game end.
   + write smart AI:
   + write the recorder driver.
     + figure out a basic featurization.  
     - multithreading?
   + make a sklearn controller
     + takes a sklearn model
     + uses the predict method to get a list of weights for different cards.
     + uses the weights to randomly try a response.
   - split into multiple files
   - fix feature engineering
'''
