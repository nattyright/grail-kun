from datetime import datetime
from time import sleep
import random
import json
from PIL import Image
import requests

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

    random.seed(datetime.now())
    random.shuffle(cards)
    return cards


def print_roll_result(cards):
    embeds = []
    for card in cards:
        if card[0] == SERVANT:
            id = card[2]
            name = FGO_SERVANT_DATA[id]['name']
            url = FGO_SERVANT_DATA[id]['face']
            class_name = FGO_SERVANT_DATA[id]['className']
        else:
            id = card[2]
            name = FGO_CE_DATA[id]['name']
            url = FGO_CE_DATA[id]['face']
            class_name = 'ce'

        embed = {'name': name, 'url': url, 'className': class_name}
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


CARD_IM = 'data/images/fgo_card/'


def get_bg_path(rank):
    return CARD_IM + 'cardgold.png' if (rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'cardsilver.png'


def get_frame_path(rank):
    return CARD_IM + 'cardgoldframe.png' if (
                rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'cardsilverframe.png'


def get_label_path(rank, class_name):
    if class_name == 'ce':
        return CARD_IM + 'cegold.png' if (rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'cesilver.png'
    else:
        return CARD_IM + 'servantgold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'servantsilver.png'


def get_stars_path(rank):
    if rank == EMBED_RANK_SSR:
        return CARD_IM + 'starssr.png'
    elif rank == EMBED_RANK_SR:
        return CARD_IM + 'starsr.png'
    else:
        return CARD_IM + 'starr.png'


def get_class_path(rank, class_name):
    if class_name == 'saber':
        return CARD_IM + 'classsabergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classsabersilver.png'
    elif class_name == 'archer':
        return CARD_IM + 'classarchergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classarchersilver.png'
    elif class_name == 'lancer':
        return CARD_IM + 'classlancergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classlancersilver.png'
    elif class_name == 'rider':
        return CARD_IM + 'classridergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classridersilver.png'
    elif class_name == 'caster':
        return CARD_IM + 'classcastergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classcastersilver.png'
    elif class_name == 'assassin':
        return CARD_IM + 'classassassingold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classassassinsilver.png'
    elif class_name == 'berserker':
        return CARD_IM + 'classberserkergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classberserkersilver.png'
    elif class_name == 'ruler':
        return CARD_IM + 'classrulergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classrulersilver.png'
    elif class_name == 'avenger':
        return CARD_IM + 'classavengergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classavengersilver.png'
    elif class_name == 'moonCancer':
        return CARD_IM + 'classmoonCancergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classmoonCancersilver.png'
    elif class_name == 'alterEgo':
        return CARD_IM + 'classalterEgogold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classalterEgosilver.png'
    elif class_name == 'foreigner':
        return CARD_IM + 'classforeignergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else CARD_IM + 'classforeignersilver.png'
    else:
        return CARD_IM + "classce.png"


# use pillow to make a roll image with the results in
# print_roll_results
def generate_ten_roll_image(results):
    card_images = []

    for result in results:
        rank = result['value']
        class_name = result['className']
        url = result['url']

        bg = Image.open(get_bg_path(rank))
        card_art = Image.open(requests.get(url, stream=True).raw)
        frame = Image.open(get_frame_path(rank))
        label = Image.open(get_label_path(rank, class_name))
        stars = Image.open(get_stars_path(rank))
        class_art = Image.open(get_class_path(rank, class_name))

        bg.paste(card_art, (6, 11))
        bg.paste(frame, (0, 0), frame)
        bg.paste(label, (6, 134))
        bg.paste(stars, (58, 108), stars)
        bg.paste(class_art, (3, 3), class_art)

        card_images.append(bg)

    result_bg = Image.open(CARD_IM + 'resultbg.png')
    y = 155
    y_delta = 180
    x1 = 70
    x2 = 220
    x_delta = 150
    card_location = [(x1, y),
                     (x1 + x_delta, y),
                     (x1 + x_delta * 2, y),
                     (x1 + x_delta * 3, y),
                     (x1 + x_delta * 4, y),
                     (x1 + x_delta * 5, y),
                     (x2, y + y_delta),
                     (x2 + x_delta, y + y_delta),
                     (x2 + x_delta * 2, y + y_delta),
                     (x2 + x_delta * 3, y + y_delta)]
    for i in range(len(card_images)):
        result_bg.paste(card_images[i], card_location[i], card_images[i])

    # result_bg.show()
    return result_bg

# generate_ten_roll_image(print_roll_result(ten_roll()))
