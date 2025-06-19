from otree.api import *
import random
from django.http import HttpResponse

doc = """
公共財ゲーム with 懲罰・メタ懲罰
"""

class C(BaseConstants):
    NAME_IN_URL = 'public_goods_punishment'
    PLAYERS_PER_GROUP = 6
    NUM_ROUNDS = 10
    
    # ゲーム設定
    CONTRIBUTION_COST = 1
    PUBLIC_GOOD_MULTIPLIER = 2
    PUNISHMENT_COST = 1
    PUNISHMENT_EFFECT = 3
    META_PUNISHMENT_COST = 1
    META_PUNISHMENT_EFFECT = 3
    
    # 一般的信頼測定
    TRUST_SCALE = [
        [1, '全くそう思わない'],
        [2, 'そう思わない'],
        [3, 'やや思わない'],
        [4, 'どちらでもない'],
        [5, 'やや思う'],
        [6, 'そう思う'],
        [7, '非常にそう思う']
    ]

class Subsession(BaseSubsession):
    def creating_session(self):
        if self.round_number == 1:
            participant_ids = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
            random.shuffle(participant_ids)
            for i, player in enumerate(self.get_players()):
                player.participant.vars['random_id'] = participant_ids[i]
                player.participant.vars['initial_points'] = 0
            # Round1 の信頼測定後にグループ分けを行うため、ここでは予備設定のみ
        else:
            # ラウンド2以降は Round1 と同じグループを維持
            self.group_like_round(1)
            # Round2以降は round1 の trust_score を保持
            for p in self.get_players():
                p.trust_score = p.in_round(1).trust_score

    def group_by_trust_score(self):
        """一般的信頼スコアに基づいてグループ分け"""
        players = self.get_players()
        # 信頼スコアでソート（常にラウンド1の値を参照）
        players_sorted = sorted(players, key=lambda p: p.in_round(1).trust_score, reverse=True)
        # 上位グループと下位グループで分ける
        group_matrix = [
            players_sorted[:C.PLAYERS_PER_GROUP],
            players_sorted[C.PLAYERS_PER_GROUP:]
        ]
        self.set_group_matrix(group_matrix)
            

class Group(BaseGroup):
    total_contribution = models.IntegerField(initial=0)
    public_pool = models.FloatField(initial=0)
    
    def calculate_payoffs(self):
        """各フェーズの報酬計算"""
        # 貢献フェーズ
        contributors = [p for p in self.get_players() if p.contribute]
        self.total_contribution = len(contributors)
        self.public_pool = self.total_contribution * C.PUBLIC_GOOD_MULTIPLIER
        public_good_per_player = self.public_pool / C.PLAYERS_PER_GROUP
        
        # 各プレイヤーの基本報酬計算
        for player in self.get_players():
            player.round_payoff = public_good_per_player
            if player.contribute:
                player.round_payoff -= C.CONTRIBUTION_COST
        
        # 懲罰フェーズ
        defectors = [p for p in self.get_players() if not p.contribute]
        for punisher in self.get_players():
            punishment_cost = 0
            for defector in defectors:
                punishment_field = f'punish_{defector.id_in_group}'
                if hasattr(punisher, punishment_field) and getattr(punisher, punishment_field):
                    punishment_cost += C.PUNISHMENT_COST
                    defector.round_payoff -= C.PUNISHMENT_EFFECT
            punisher.round_payoff -= punishment_cost
        
        # メタ懲罰フェーズ
        for meta_punisher in self.get_players():
            meta_punishment_cost = 0
            for defector in defectors:
                # この裏切り者を懲罰しなかった人を特定
                non_punishers = []
                for player in self.get_players():
                    if player != defector:  # 自分自身は除く
                        punishment_field = f'punish_{defector.id_in_group}'
                        if not (hasattr(player, punishment_field) and getattr(player, punishment_field)):
                            non_punishers.append(player)
                
                # 非懲罰者に対するメタ懲罰
                for non_punisher in non_punishers:
                    meta_punishment_field = f'meta_punish_{non_punisher.id_in_group}'
                    if hasattr(meta_punisher, meta_punishment_field) and getattr(meta_punisher, meta_punishment_field):
                        meta_punishment_cost += C.META_PUNISHMENT_COST
                        non_punisher.round_payoff -= C.META_PUNISHMENT_EFFECT
            
            meta_punisher.round_payoff -= meta_punishment_cost
        
        # 累積報酬更新
        for player in self.get_players():
            player.participant.vars['initial_points'] = (
                player.participant.vars.get('initial_points', 0)
                + player.round_payoff
            )

class Player(BasePlayer):
    # 一般的信頼測定
    trust_q1 = models.IntegerField(
        label='他者は善意を持っていると思う',
        choices=C.TRUST_SCALE,
        widget=widgets.RadioSelect
    )
    trust_q2 = models.IntegerField(
        label='人の話は信用できると思う',
        choices=C.TRUST_SCALE,
        widget=widgets.RadioSelect
    )
    trust_q3 = models.IntegerField(
        label='人が裏の意図を持っていると疑う',
        choices=C.TRUST_SCALE,
        widget=widgets.RadioSelect
    )
    trust_score = models.FloatField(initial=0)
    
    # ゲーム行動
    contribute = models.BooleanField(
        label='公共のプールに貢献しますか？',
        choices=[[True, 'はい（貢献する）'], [False, 'いいえ（貢献しない）']],
        widget=widgets.RadioSelect
    )
    
    # 懲罰決定（動的フィールド）
    punish_1 = models.BooleanField(blank=True)
    punish_2 = models.BooleanField(blank=True)
    punish_3 = models.BooleanField(blank=True)
    punish_4 = models.BooleanField(blank=True)
    punish_5 = models.BooleanField(blank=True)
    punish_6 = models.BooleanField(blank=True)
    
    # メタ懲罰決定（動的フィールド）
    meta_punish_1 = models.BooleanField(blank=True)
    meta_punish_2 = models.BooleanField(blank=True)
    meta_punish_3 = models.BooleanField(blank=True)
    meta_punish_4 = models.BooleanField(blank=True)
    meta_punish_5 = models.BooleanField(blank=True)
    meta_punish_6 = models.BooleanField(blank=True)
    
    # 報酬
    round_payoff = models.FloatField(initial=0)

    # 確認フラグ
    confirmed = models.BooleanField(initial=False)
    
    def calculate_trust_score(self):
        """一般的信頼スコア計算"""
        # 3番目の項目は逆転項目
        reversed_q3 = 8 - self.trust_q3
        self.trust_score = (self.trust_q1 + self.trust_q2 + reversed_q3) / 3

# ページクラス
class GeneralTrust(Page):
    form_model = 'player'
    
    def get_form_fields(self):
        if self.round_number == 1:
            return ['trust_q1', 'trust_q2', 'trust_q3']

    def before_next_page(self, timeout_happened):
        if self.round_number == 1:
            self.calculate_trust_score()
        else:
            self.trust_score = self.in_round(1).trust_score

class GeneralTrustWaitPage(WaitPage):
    wait_for_all_groups = True
    def after_all_players_arrive(self):
        self.subsession.group_by_trust_score()
        
class Contribution(Page):
    form_model = 'player'
    form_fields = ['contribute']
    
    def vars_for_template(self):
        return {
            'round_number': self.round_number,
            'player_id': self.participant.vars.get('random_id', ''),
            'current_points': self.participant.vars.get('initial_points', 0)
        }

class ContributionWaitPage(WaitPage):
    wait_for_all_groups = True
class Punishment(Page):
    form_model = 'player'
    
    def get_form_fields(self):
        # 裏切り者がいる場合のみ表示
        defectors = [p for p in self.group.get_players() if not p.contribute]
        if not defectors:
            return []
        
        form_fields = []
        for defector in defectors:
            form_fields.append(f'punish_{defector.id_in_group}')
        return form_fields
    
    def is_displayed(self):
        # 裏切り者がいる場合のみ表示
        defectors = [p for p in self.group.get_players() if not p.contribute]
        return len(defectors) > 0
    
    def vars_for_template(self):
        defectors = [p for p in self.group.get_players() if not p.contribute]
        defector_info = []
        for defector in defectors:
            defector_info.append({
                'id': defector.id_in_group,
                'name': defector.participant.vars.get('random_id', ''),
                'field_name': f'punish_{defector.id_in_group}'
            })
        
        return {
            'defectors': defector_info,
            'player_id': self.participant.vars.get('random_id', '')
        }

class PunishmentWaitPage(WaitPage):
    wait_for_all_groups = True

class MetaPunishment(Page):
    form_model = 'player'
    
    def get_form_fields(self):
        # 裏切り者を懲罰しなかった人がいる場合のみ表示
        defectors = [p for p in self.group.get_players() if not p.contribute]
        non_punishers = []
        
        for defector in defectors:
            for player in self.group.get_players():
                if player != defector:
                    punishment_field = f'punish_{defector.id_in_group}'
                    if not (hasattr(player, punishment_field) and getattr(player, punishment_field)):
                        if player not in non_punishers:
                            non_punishers.append(player)
        
        if not non_punishers:
            return []
        
        form_fields = []
        for non_punisher in non_punishers:
            form_fields.append(f'meta_punish_{non_punisher.id_in_group}')
        return form_fields
    
    def is_displayed(self):
        # 裏切り者を懲罰しなかった人がいる場合のみ表示
        defectors = [p for p in self.group.get_players() if not p.contribute]
        for defector in defectors:
            for player in self.group.get_players():
                if player != defector:
                    punishment_field = f'punish_{defector.id_in_group}'
                    if not (hasattr(player, punishment_field) and getattr(player, punishment_field)):
                        return True
        return False
    
    def vars_for_template(self):
        defectors = [p for p in self.group.get_players() if not p.contribute]
        non_punishers = []
        
        for defector in defectors:
            for player in self.group.get_players():
                if player != defector:
                    punishment_field = f'punish_{defector.id_in_group}'
                    if not (hasattr(player, punishment_field) and getattr(player, punishment_field)):
                        if player not in non_punishers:
                            non_punishers.append(player)
        
        non_punisher_info = []
        for non_punisher in non_punishers:
            non_punisher_info.append({
                'id': non_punisher.id_in_group,
                'name': non_punisher.participant.vars.get('random_id', ''),
                'field_name': f'meta_punish_{non_punisher.id_in_group}'
            })
        
        return {
            'non_punishers': non_punisher_info,
            'player_id': self.participant.vars.get('random_id', '')
        }

class MetaPunishmentWaitPage(WaitPage):
    def after_all_players_arrive(self):
        # 報酬計算はここで行う
        self.group.calculate_payoffs()

class Results(Page):
    form_model = 'player'
    form_fields = ['confirmed']

    def is_displayed(self):
        return self.round_number == C.NUM_ROUNDS

    def vars_for_template(self):
        # グループメンバーの結果情報
        group_results = []
        for p in self.group.get_players():
            # 懲罰情報の取得
            punishment_info = []
            defectors = [d for d in self.group.get_players() if not d.contribute]
            for d in defectors:
                field = f'punish_{d.id_in_group}'
                if p.field_maybe_none(field):
                    punishment_info.append(
                        f"{d.participant.vars.get('random_id', '')}懲罰"
                    )

            # メタ懲罰情報の取得
            meta_info = []
            for other in self.group.get_players():
                if other is not p:
                    field = f'meta_punish_{other.id_in_group}'
                    if p.field_maybe_none(field):
                        meta_info.append(
                            f"{other.participant.vars.get('random_id', '')}メタ懲罰"
                        )

            group_results.append({
                'name': p.participant.vars.get('random_id', ''),
                'contributed': '貢献した' if p.contribute else '貢献しなかった',
                'punishment': ', '.join(punishment_info) or '懲罰なし',
                'meta_punishment': ', '.join(meta_info) or 'メタ懲罰なし',
                # p は Player、self はページを呼び出した Player
                'round_payoff': f"{p.round_payoff:.2f}",
                'total_payoff': f"{p.participant.vars.get('initial_points', 0):.2f}",
            })

        return {
            'group_results': group_results,
            'round_number': self.round_number,
            'total_contribution': self.group.total_contribution,
            'public_pool': f"{self.group.public_pool:.2f}",
            'player_id': self.participant.vars.get('random_id', ''),
            # ここを self.player → self に修正
            'player_round_payoff': f"{self.round_payoff:.2f}",
            'player_total_payoff': f"{self.participant.vars.get('initial_points', 0):.2f}",
        }

            
page_sequence = [
    GeneralTrust,
    GeneralTrustWaitPage,
    Contribution,
    ContributionWaitPage,
    Punishment,
    PunishmentWaitPage,
    MetaPunishment,
    MetaPunishmentWaitPage,
    Results
]

