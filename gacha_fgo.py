from datetime import datetime
from time import sleep
import random
import json
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

TEN_ROLL_COUNT = 11
BANNER_TITLE = 'servant_fes_rerun_1'
SERVANT_ART_PATH = 'data/images/fgo_servant/'
SERVANT_CHARAGRAPH_PATH = 'data/images/fgo_servant_charagraph/'
CE_ART_PATH = 'data/images/fgo_ce/'
CE_CHARAGRAPH_PATH = 'data/images/fgo_ce_charagraph/'
UI_ART_PATH = 'data/images/fgo_card/'

# enums
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

BANNER_DATA = {}
RATES = {'SSR' : {'servant': 0, 'ce': 0}, 'SR': {'servant': 0, 'ce': 0}, 'R': {'servant': 0, 'ce': 0}}


with open("data/fgo_servant.json", "r", encoding="utf-8") as to_read:
    global FGO_SERVANT_DATA
    FGO_SERVANT_DATA = json.load(to_read)
with open("data/fgo_ce.json", "r", encoding="utf-8") as to_read:
    global FGO_CE_DATA
    FGO_CE_DATA = json.load(to_read)


#get banner data
def get_banner_data(banner_name):
    with open("data/fgo_gacha.json", "r", encoding="utf-8") as to_read:
        global BANNER_DATA
        global RATES
        BANNER_DATA = json.load(to_read)[banner_name]

        RATES['SSR']['servant'] = BANNER_DATA['SSR']['servant']['rate'] / 0.01
        RATES['SR']['servant'] = BANNER_DATA['SR']['servant']['rate'] / 0.03
        RATES['R']['servant'] = BANNER_DATA['R']['servant']['rate'] / 0.4
        RATES['SSR']['ce'] = BANNER_DATA['SSR']['ce']['rate'] / 0.04
        RATES['SR']['ce'] = BANNER_DATA['SR']['ce']['rate'] / 0.12
        RATES['R']['ce'] = BANNER_DATA['R']['ce']['rate'] / 0.4
        #print(RATES['SSR']['servant'],RATES['SR']['servant'],RATES['R']['servant'])
        #print(RATES['SSR']['ce'],RATES['SR']['ce'],RATES['R']['ce'])


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
        rate += RATES[card_rank][card_type]
        if rate > 0 and rand < rate:
            return BANNER_DATA[card_rank][card_type]['up'][i]

    normal = get_random_num_whole(len(BANNER_DATA[card_rank][card_type]['normal']))
    return BANNER_DATA[card_rank][card_type]['normal'][normal]


def summon_once_normally():
    rand = get_random_num()
    if rand >= 0.99:
        # SSR Servant 1%
        r = (rand - 0.99) / 0.01
        card = SERVANT, 5, summon_from_pool('servant', 'SSR', r)
    elif 0.95 <= rand < 0.99:
        # SSR CE 4%
        r = (rand - 0.95) / 0.04
        card = CE, 5, summon_from_pool('ce', 'SSR', r)
    elif 0.92 <= rand < 0.95:
        # SR Servant 3%
        r = (rand - 0.92) / 0.03
        card = SERVANT, 4, summon_from_pool('servant', 'SR', r)
    elif 0.8 <= rand < 0.92:
        # SR CE 12%
        r = (rand - 0.8) / 0.12
        card = CE, 4, summon_from_pool('ce', 'SR', r)
    elif 0.4 <= rand < 0.8:
        # R Servant 40%
        r = (rand - 0.4) / 0.4
        card = SERVANT, 3, summon_from_pool('servant', 'R', r)
    else:
        # R CE 40%
        r = (rand - 0.0) / 0.4
        card = CE, 3, summon_from_pool('ce', 'R', r)
    #print(r)
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


def ten_roll(banner_name):
    get_banner_data(banner_name)
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


def single_roll(banner_name):
    get_banner_data(banner_name)
    card = summon_once_normally()
    if card[0] == SERVANT:
        has_servant = True
    if card[1] == SSR or card[1] == SR:
        has_gold = True
    return card


def print_roll_result(cards):
    embeds = []
    for card in cards:
        id = str(card[2])
        if card[0] == SERVANT:
            url = SERVANT_ART_PATH + str(id).zfill(3) + '.png'
            class_name = FGO_SERVANT_DATA[id]['className']
        else:
            url = CE_ART_PATH + str(id).zfill(3) + '.png'
            class_name = FGO_CE_DATA[id]['className']

        embed = {'url': url, 'className': class_name}
        if card[1] == SSR:
            embed['value'] = EMBED_RANK_SSR
        elif card[1] == SR:
            embed['value'] = EMBED_RANK_SR
        else:
            embed['value'] = EMBED_RANK_R

        embeds.append(embed)
    return embeds


def print_roll_result_single(card):
    id = str(card[2])

    if card[0] == SERVANT:
        url = SERVANT_CHARAGRAPH_PATH + str(id) + '.png'
        class_name = FGO_SERVANT_DATA[id]['className']
    else:
        url = CE_CHARAGRAPH_PATH + str(id) + '.png'
        class_name = FGO_CE_DATA[id]['className']

    embed = {'url': url, 'className': class_name}
    if card[1] == SSR:
        embed['value'] = EMBED_RANK_SSR
    elif card[1] == SR:
        embed['value'] = EMBED_RANK_SR
    else:
        embed['value'] = EMBED_RANK_R

    return embed


def get_bg_path(rank):
    return UI_ART_PATH + 'cardgold.png' if (rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'cardsilver.png'


def get_frame_path(rank):
    return UI_ART_PATH + 'cardgoldframe.png' if (
                rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'cardsilverframe.png'


def get_label_path(rank, class_name):
    if class_name == 'ce':
        return UI_ART_PATH + 'cegold.png' if (rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'cesilver.png'
    else:
        return UI_ART_PATH + 'servantgold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'servantsilver.png'


def get_stars_path(rank):
    if rank == EMBED_RANK_SSR:
        return UI_ART_PATH + 'starssr.png'
    elif rank == EMBED_RANK_SR:
        return UI_ART_PATH + 'starsr.png'
    else:
        return UI_ART_PATH + 'starr.png'


def get_class_path(rank, class_name):
    if class_name == 'saber':
        return UI_ART_PATH + 'classsabergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classsabersilver.png'
    elif class_name == 'archer':
        return UI_ART_PATH + 'classarchergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classarchersilver.png'
    elif class_name == 'lancer':
        return UI_ART_PATH + 'classlancergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classlancersilver.png'
    elif class_name == 'rider':
        return UI_ART_PATH + 'classridergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classridersilver.png'
    elif class_name == 'caster':
        return UI_ART_PATH + 'classcastergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classcastersilver.png'
    elif class_name == 'assassin':
        return UI_ART_PATH + 'classassassingold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classassassinsilver.png'
    elif class_name == 'berserker':
        return UI_ART_PATH + 'classberserkergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classberserkersilver.png'
    elif class_name == 'ruler':
        return UI_ART_PATH + 'classrulergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classrulersilver.png'
    elif class_name == 'avenger':
        return UI_ART_PATH + 'classavengergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classavengersilver.png'
    elif class_name == 'moonCancer':
        return UI_ART_PATH + 'classmooncancergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classmooncancersilver.png'
    elif class_name == 'alterEgo':
        return UI_ART_PATH + 'classalteregogold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classalteregosilver.png'
    elif class_name == 'foreigner':
        return UI_ART_PATH + 'classforeignergold.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classforeignersilver.png'
    else:
        return UI_ART_PATH + "classce.png"


# use pillow to make a roll image with the results in
# print_roll_results
def generate_ten_roll_image(results):
    card_images = []

    for result in results:
        rank = result['value']
        class_name = result['className']
        url = result['url']

        bg = Image.open(get_bg_path(rank))
        card_art = Image.open(url) #downloaded img in directory - open directly
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

    result_bg = Image.open(UI_ART_PATH + 'resultbg.png')
    y = 155
    y_delta = 180
    x1 = 65
    x2 = 140
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
                     (x2 + x_delta * 3, y + y_delta),
                     (x2 + x_delta * 4, y + y_delta)]
    for i in range(len(card_images)):
        result_bg.paste(card_images[i], card_location[i], card_images[i])

    # result_bg.show()
    return result_bg

# generate_ten_roll_image(print_roll_result(ten_roll()))



def get_bg_path_single(class_name):
    if class_name == 'ce':
        return UI_ART_PATH + 'charagraph_bg_ce.png'
    else:
        return UI_ART_PATH + 'charagraph_bg_servant.png'


def get_frame_path_single(rank, class_name):
    frame_path_start = UI_ART_PATH + 'charagraph_'
    frame_path_end = '.png'

    if class_name == 'ce':
        frame_path_mid = 'ce_'
    else:
        frame_path_mid = 'servant_'

    if rank == EMBED_RANK_SSR:
        frame_path_mid += '05'
    elif rank == EMBED_RANK_SR:
        frame_path_mid += '04'
    elif rank == EMBED_RANK_R:
        frame_path_mid += '03'

    return frame_path_start + frame_path_mid + frame_path_end


def get_class_path_single(rank, class_name):
    if class_name == 'saber':
        return UI_ART_PATH + 'classsabergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classsabersilver_charagraph.png'
    elif class_name == 'archer':
        return UI_ART_PATH + 'classarchergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classarchersilver_charagraph.png'
    elif class_name == 'lancer':
        return UI_ART_PATH + 'classlancergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classlancersilver_charagraph.png'
    elif class_name == 'rider':
        return UI_ART_PATH + 'classridergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classridersilver_charagraph.png'
    elif class_name == 'caster':
        return UI_ART_PATH + 'classcastergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classcastersilver_charagraph.png'
    elif class_name == 'assassin':
        return UI_ART_PATH + 'classassassingold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classassassinsilver_charagraph.png'
    elif class_name == 'berserker':
        return UI_ART_PATH + 'classberserkergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classberserkersilver_charagraph.png'
    elif class_name == 'ruler':
        return UI_ART_PATH + 'classrulergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classrulersilver_charagraph.png'
    elif class_name == 'avenger':
        return UI_ART_PATH + 'classavengergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classavengersilver_charagraph.png'
    elif class_name == 'moonCancer':
        return UI_ART_PATH + 'classmooncancergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classmooncancersilver_charagraph.png'
    elif class_name == 'alterEgo':
        return UI_ART_PATH + 'classalteregogold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classalteregosilver_charagraph.png'
    elif class_name == 'foreigner':
        return UI_ART_PATH + 'classforeignergold_charagraph.png' if (
                    rank == EMBED_RANK_SSR or rank == EMBED_RANK_SR) else UI_ART_PATH + 'classforeignersilver_charagraph.png'
    else:
        return UI_ART_PATH + "classce.png"


# use pillow to make a roll image with the results in
# print_roll_results
def generate_single_roll_image(result):

    rank = result['value']
    class_name = result['className']
    url = result['url']

    bg = Image.open(get_bg_path_single(class_name))
    card_art = Image.open(url) #downloaded img in directory - open directly
    frame = Image.open(get_frame_path_single(rank, class_name))
    class_art = Image.open(get_class_path_single(rank, class_name))

    if class_name == 'ce':
        bg.paste(card_art, (0, 0), bg)
    else:
        bg.paste(card_art, (4, 20))
    bg.paste(frame, (0, 0), frame)
    bg.paste(class_art, (104, 368), class_art)

    font = ImageFont.truetype(UI_ART_PATH + 'honoka.ttf', 24)
    font2 = ImageFont.truetype(UI_ART_PATH + 'honoka.ttf', 13)
    msg = "Salt Sim"
    msg2 = "Did you get what you wanted?w?"
    bg_draw = ImageDraw.Draw(bg)
    W, H = 244, 418
    w, h = bg_draw.textsize(msg, font=font)
    w2, h2 = bg_draw.textsize(msg2, font=font2)
    bg_draw.text(((W-w)/2, 335), msg,
                 font=font, fill='rgb(255, 255, 255)',
                 stroke_width=1, stroke_fill='rgb(0, 0, 0)')
    bg_draw.text(((W - w2) / 2, 360), msg2,
                 font=font2, fill='rgb(255, 255, 255)',
                 stroke_width=1, stroke_fill='rgb(0, 0, 0)')

    result_bg = Image.open(UI_ART_PATH + 'resultbg_single.png')
    y = 56
    x = 387
    card_location = (x, y)

    result_bg.paste(bg, card_location, bg)

    #result_bg.show()
    return result_bg


#generate_single_roll_image(print_roll_result_single(single_roll('servant_fes_rerun_2')))