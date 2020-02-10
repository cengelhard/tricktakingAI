
from pyrsistent import (PRecord, field,
						pset_field, PSet, s, pset,
						m, pmap,
						CheckedPVector, pvector_field, PVector, v, pvector,
						l, plist)

suit_names =pmap({"♠": "Spades",
				  "♥": "Hearts",
				  "♦": "Diamonds",
				  "♣": "Clubs"})
suit_keys = v("♠","♥","♦","♣")
rank_names = v('2','3','4','5','6','7','8','9','10','J','Q','K','A')

class Card(PRecord):
	suit = field(str)
	rank = field(int)
	key  = field(str)
	name = field(str)

#recommend use this if you must create one.
def card(r,s):
	return Card(suit=s, rank=r, key=f"{rank_names[r]}{s}", name=f"{rank_names[r]} of {suit_names[s]}")

#but this is probably where you'll be getting the cards from:
#the indecies of this list are used in most places instead of the actual Card objects.
deck52 = pvector([card(r,s) for r in range(13) for s in suit_keys])


