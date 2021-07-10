from datetime import datetime
from time import sleep
import random
import json

TEN_ROLL_COUNT = 10

SSR_SERVANT_UP = 0.007
SR_SERVANT_UP = 0.012
R_SERVANT_UP = 0.0

SSR_CE_UP = 0.028
SR_CE_UP = 0.04
R_CE_UP = 0.08

BANNER_TITLE = 'servant_fes_rerun_1'

SERVANT = 0
CE = 1
SSR = 5
SR = 4
R = 3
EMBED_COLOR_GOLD = 16763904
EMBED_COLOR_SILVER = 13553358
EMBED_RANK_SSR = '★★★★★'
EMBED_RANK_SR = '★★★★'
EMBED_RANK_R = '★★★'


with open("data/fgo_gacha.json", "r", encoding="utf-8") as to_read:
    global BANNER_DATA
    BANNER_DATA = json.load(to_read)[BANNER_TITLE]
with open("data/fgo_servant.json", "r", encoding="utf-8") as to_read:
    global FGO_SERVANT_DATA
    FGO_SERVANT_DATA = {}
    data = json.load(to_read)
    for item in data:
        FGO_SERVANT_DATA[item['collectionNo']] = item
with open("data/fgo_ce.json", "r", encoding="utf-8") as to_read:
    global FGO_CE_DATA
    FGO_CE_DATA = {}
    data = json.load(to_read)
    for item in data:
        FGO_CE_DATA[item['collectionNo']] = item


def get_random_num():
    sleep(0.05)
    random.seed(datetime.now())
    return random.random()


def get_random_num_whole(range):
    sleep(0.05)
    random.seed(datetime.now())
    return random.randrange(range)


def summon_from_pool(card_type, card_rank, rand):
    rate = 0
    for i in range(len(BANNER_DATA[card_rank][card_type]['up'])):
        rate += SSR_SERVANT_UP
        if rand < rate:
            return BANNER_DATA[card_rank][card_type]['up'][i]

    normal = get_random_num_whole(len(BANNER_DATA[card_rank][card_type]['normal']))
    return BANNER_DATA[card_rank][card_type]['normal'][normal]


def summon_once_normally():
    rand = get_random_num()
    if rand >= 0.99:
        # SSR Servant 1%
        card = SERVANT, 5, summon_from_pool('servant', 'SSR', rand)
    elif 0.95 <= rand < 0.99:
        # SSR CE 4%
        card = CE, 5, summon_from_pool('ce', 'SSR', rand)
    elif 0.92 <= rand < 0.95:
        # SR Servant 3%
        card = SERVANT, 4, summon_from_pool('servant', 'SR', rand)
    elif 0.8 <= rand < 0.92:
        # SR CE 12%
        card = CE, 4, summon_from_pool('ce', 'SR', rand)
    elif 0.4 <= rand < 0.8:
        # R Servant 40%
        card = SERVANT, 3, summon_from_pool('servant', 'R', rand)
    else:
        # R CE 40%
        card = CE, 3, summon_from_pool('ce', 'R', rand)

    #print(card)
    return card


def summon_pity_gold_card():
    rand = get_random_num()
    if rand >= 0.95:
        # SSR Servant 5%
        card = SERVANT, 5, summon_from_pool('servant', 'SSR', rand)
    elif 0.75 <= rand < 0.95:
        # SSR CE 20%
        card = CE, 5, summon_from_pool('ce', 'SSR', rand)
    elif 0.60 <= rand < 0.75:
        # SR Servant 15%
        card = SERVANT, 4, summon_from_pool('servant', 'SR', rand)
    else:
        # SR CE 60%
        card = CE, 4, summon_from_pool('ce', 'SR', rand)

    #print(card)
    return card


def summon_pity_servant():
    rand = get_random_num()

    ssr_rate = 1.0 / 44
    ssr_threshold = 1 - ssr_rate
    sr_rate = 3.0 / 44
    sr_threshold = ssr_threshold - sr_rate
    r_rate = 40.0 / 44
    r_threshold = sr_threshold - r_rate

    if rand >= ssr_threshold:
        # SSR Servant
        card = SERVANT, 5, summon_from_pool('servant', 'SSR', rand)
    elif sr_threshold <= rand < ssr_threshold:
        # SR Servant
        card = SERVANT, 4, summon_from_pool('servant', 'SR', rand)
    else:
        # R Servant
        card = SERVANT, 3, summon_from_pool('servant', 'R', rand)

    #print(card)
    return card


def ten_roll():
    has_gold = False
    has_servant = False
    cards = []
    # first (n-2) cards are random
    for i in range(TEN_ROLL_COUNT - 2):
        card = summon_once_normally()
        cards.append(card)
        if card[0] == SERVANT:
            has_servant = True
        if card[1] == SSR or card[1] == SR:
            has_gold = True

    # if no gold, (n-1)th card will be gold
    if not has_gold:
        card = summon_pity_gold_card()
        cards.append(card)
        if card[0] == SERVANT:
            has_servant = True
    else:
        card = summon_once_normally()
        cards.append(card)
    # if no servant, nth card will be servant
    if not has_servant:
        card = summon_pity_servant()
        cards.append(card)
    else:
        card = summon_once_normally()
        cards.append(card)

    #random.seed(datetime.now())
    #random.shuffle(cards)
    return cards

def print_roll_result(cards):
    embeds = []
    for card in cards:
        if card[0] == SERVANT:
            id = card[2]
            name = FGO_SERVANT_DATA[id]['name']
            url = FGO_SERVANT_DATA[id]['face']
        else:
            id = card[2]
            name = FGO_CE_DATA[id]['name']
            url = FGO_CE_DATA[id]['face']

        embed = {}
        embed['name'] = name
        embed['url'] = url
        if card[1] == SSR:
            embed['color'] = EMBED_COLOR_GOLD
            embed['value'] = EMBED_RANK_SSR
        elif card[1] == SR:
            embed['color'] = EMBED_COLOR_GOLD
            embed['value'] = EMBED_RANK_SR
        else:
            embed['color'] = EMBED_COLOR_SILVER
            embed['value'] = EMBED_RANK_R

        embeds.append(embed)

    return embeds

#print_roll_result(ten_roll())
