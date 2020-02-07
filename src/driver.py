

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
from learnController import sklearn_controller_raw, np_from_controllers, default_controllers

from sklearn.neural_network import MLPRegressor
from sklearn.linear_model   import LinearRegression, LogisticRegression
from sklearn.ensemble       import RandomForestRegressor
from sklearn.ensemble       import GradientBoostingRegressor

from sklearn.metrics import mean_squared_error as mse
from sklearn.base    import clone as sk_clone

import numpy as np

#rand.seed(42)

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
	return total_points

def quick_play(num_games, *names):
	return play_from_cast(names, HeartsGame(pass_phase=False, num_hands=1), num_games)

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

sklearn_model_cast = {
	
}

def make_cast(name, skl_model):
	def init(amount_of_data=10):
		controller_cast[name] = sklearn_controller_raw(skl_model, amount_of_data=amount_of_data)
		controller_cast[name+"*"] = sklearn_controller_raw(skl_model, amount_of_data=0, look_ahead=True)
		sklearn_model_cast[name] = skl_model
	return init

Krang     = make_cast("Krang", MLPRegressor(activation='relu', hidden_layer_sizes= (200, 200, 50), learning_rate='adaptive', max_iter=500))	
Galadriel = make_cast("Galadriel", RandomForestRegressor(criterion='mse', max_features=100, n_estimators=800))
Peppy     = make_cast("Peppy", GradientBoostingRegressor(n_estimators=200))
Walter    = make_cast("Walter", LinearRegression())
GlaDOS    = make_cast("GlaDOS", LogisticRegression())

cast_factories = {
	'Krang':     Krang,
	'Galadriel': Galadriel,
	'Peppy':     Peppy,
	'Walter':    Walter,
}

def learn_all(amount_of_data=10):
	 Krang(amount_of_data)
	 Walter(amount_of_data)
	 Galadriel(amount_of_data)
	 Peppy(amount_of_data)

from joblib import dump, load

def dump_name(name):
	dump(sklearn_model_cast[name], f"{name}.joblib")

def load_name(name):
	try:
		skl_model = load(f"{name}.joblib")
		make_cast(name, skl_model)(amount_of_data=0)
		sklearn_model_cast[name] = skl_model
	except:
		pass

def load_all():
	load_name("Krang")
	load_name("Galadriel")
	load_name("Peppy")
	load_name("Walter")

from sklearn.model_selection import GridSearchCV


def grid_search(model_type, params):
	def search():
		model = model_type()
		clf = GridSearchCV(model, params, n_jobs=-1, verbose=10, cv=4)
		X,y = np_from_controllers(default_controllers, 250)
		clf.fit(X,y)

		print("Best parameters set found on development set:")
		print(clf.best_params_)
		return model
	return search


#{'criterion': 'mse', 'max_features': 15, 'n_estimators': 150}
grid_search_rforest = grid_search(RandomForestRegressor, {
		'max_features': [100, 150, 200],
		'n_estimators': [200, 400, 800],
		'criterion'   : ['mse']
	})

#Best parameters set found on development set:
#{'activation': 'tanh', 'hidden_layer_sizes': (20, 20, 20), 'learning_rate': 'adaptive'}
#{'activation': 'tanh', 'hidden_layer_sizes': 120}
grid_search_mlp = grid_search(MLPRegressor, {
		'hidden_layer_sizes': [(200, 50, 50), (50, 50, 50), (200, 200, 200), (200, 200, 50)],
		'activation'        : ['relu', 'tanh'],
		'learning_rate'     : ['adaptive']
	})

grid_search_gboost = grid_search(GradientBoostingRegressor, {
		'loss'          : ['ls', 'huber', 'quantile'],
		'learning_rate' : [0.1, 0.01, 0.001],
		'n_estimators'  : [100, 200, 400]
	})

default_self_play = ["Krang", "Peppy", "Walter", "Galadriel"]
def self_play(generations=3, cast = default_self_play):
	load_all()
	controllers = default_controllers#[controller_cast[name](i) for i,name in enumerate(cast)]
	skmodels    = [sklearn_model_cast[name] for name in cast]
	for gen_num in range(generations):
		print(f"-------- generation {gen_num} --------")
		controllers = [sklearn_controller_raw(sklearn_model_cast[name], 
											  controllers, 
											  amount_of_data=100)(i)
						for i,name in enumerate(cast)]
	for i, controller in enumerate(controllers):
		controller_cast[cast[i]]=controller


def deedee_fight(names, iterations=40, start=50, step=50, games_to_play=50, samples=4):
	points_by_name = {name: [] for name in names}
	xs = np.arange(start,start + step*iterations,step)
	for data in xs:
		tup = np_from_controllers(iterations=data, samples=samples) #use default controllers to train.
		for name in names:
			cont_factory = cast_factories.get(name)
			if cont_factory:
				cont_factory(amount_of_data=tup)
			results = quick_play(games_to_play, name, "Deedee", "Deedee", "Deedee")
			points_by_name[name].append(results[0]/sum(results))
	def graph_it(ax):
		for name, ys in points_by_name.items():
			ax.plot(xs*samples, np.array(ys)/games_to_play, label=name)
		ax.legend()
		ax.set_xlabel("training set size")
		ax.set_ylabel("average score")
		return ax
	return points_by_name, graph_it

def ugh(ax, stats):
	xs = np.arange(100,100*(20+1),100)
	for name in ["Walter", "Peppy", "Galadriel", "Krang"]: 
		ys = stats[name] 
		ax.scatter(xs*4, np.array(ys), marker='.')
		line = np.poly1d(np.polyfit(xs,ys,3))
		ax.plot(xs*4, [line(x) for x in xs], label=name)
	ax.plot([0,8000], [0.25, 0.25], label="Deedee avg")
	ax.plot([0,8000], [0.159, 0.159], label="Dexter avg")
	ax.legend(loc='best')
	ax.set_xlabel("training set size")
	ax.set_ylabel("average score %")
	ax.set_ylim(0.1,0.3)
	ax.set_title("AIs vs. 3 Deedees")

'''
TODO:
	- refactor View to use a Trick object.
	- implement self-play
	+ make something that can beat Dexter
	- impement the pass phase.
	- make some very large datasets
	- optimize the learning process
	- make look-ahead worthwhile






'''
