from otree.api import *  # oTree imports
import random  # for random choice and advisor probability
import math


doc = """
Eksperiment finančnega odločanja v socialnem okolju

V vsakem krogu boste razporejeni v skupino z več drugimi udeleženci.
Vsaki skupini bo naključno dodeljena ena uspešna investicijska možnost (A ali B).
Člani skupine bodo svoje odločitve sprejemali zaporedno, eden za drugim.
Pred sprejemom odločitve boste prejeli priporočilo svetovalca. Priporočilo je lahko pravilno ali nepravilno, saj je njegova točnost odvisna od natančnosti svetovalca. Ob priporočilu bo prikazana tudi stopnja prepričanosti svetovalca v pravilnost njegovega nasveta. Sami se odločite, ali boste priporočilo upoštevali ali ga prezrli.
Če niste prvi član skupine, boste pred sprejemom odločitve videli tudi odločitve predhodnih članov skupine.
V prvem krogu se lahko odločite tudi, da ne izberete nobene možnosti. V vseh naslednjih krogih bo izbira ene izmed ponujenih možnosti obvezna.
Na podlagi razpoložljivih informacij boste izbrali investicijsko možnost A ali B.
Če izberete uspešno investicijsko možnost, prejmete nagrado. Če izberete neuspešno možnost, ne prejmete nagrade oziroma prejmete kazen, če je ta določena. Od vseh izplačil se odštejejo transakcijski stroški.
Po vsakem krogu boste prerazporejeni v novo skupino z drugimi udeleženci.
Po zaključku eksperimenta boste videli svoj skupni rezultat ter število primerov, ko ste sledili priporočilu svetovalca.
Sodelovanje v eksperimentu je popolnoma anonimno. Vsi zbrani podatki bodo obravnavani zaupno in uporabljeni izključno za namene raziskave.
Vse informacije, prikazane v eksperimentu, vključno s cenami, donosi, stroški in morebitnimi nagradami, so fiktivne ter namenjene izključno simulaciji investicijskega odločanja.
"""

# --------------------------------------------------------------------
# Constants - Experiment Configuration
# --------------------------------------------------------------------
class C(BaseConstants):
    NAME_IN_URL = 'social_investment' # URL name for the app (u can change it to display different name in URL)
    PLAYERS_PER_GROUP = 4 # Number of players/participants per group
    #NUM_GROUPS = 3 # Number of groups per round # can be changed in otree site directly based on total participants so this becaomes useless
    NUM_ROUNDS = 3 # Total number of rounds in the experiment
    #TOTAL_PLAYERS = PLAYERS_PER_GROUP * NUM_GROUPS # Total number of players in the experiment
    OPTION_A = 'A'
    OPTION_B = 'B'
    CHOICES = [OPTION_A, OPTION_B] # Possible investment options
    WEIGHTS = [45, 55] # Weights for random selection of successful option (45% for A, 55% for B)
    CORRECT_CHOICE_REWARD = cu(10) # Reward for choosing the correct option
    INCORRECT_CHOICE_PENALTY = cu(5) # Penalty for incorrect choice (if any)
    OTHER_PLAYERS = PLAYERS_PER_GROUP - 1 # Number of other players in the group (Just for HTML template)
    ADVISOR_CORRECTION_THRESHOLD_PERCENT = 60 # Percentage chance (0-100) that the advisor gives correct advice (Advisor tells truth if random percentage < threshold)
    # Round Specific Constants
    ENDOWMENT = [cu(0), cu(11), cu(11)] # Initial endowment for each player at the start of each round 1,2,3 respectively
    ALLOW_ABSTAIN = [True, False, False] # Whether players can abstain from investing in each round 1,2,3 respectively
    ABSTAIN = 'Abstain' # Option for abstaining from investment (only in round 1)
    TRANSACTION_COSTS = [cu(0), cu(0), [cu(0.1), cu(0.5)]] # Cost deducted from payoffs in each round 1,2,3 respectively / in round 3 different transaction costs for option A and B
    STOCK_PRICES = [cu(2), cu(4), cu(6)]  # Round 1 = fixed price, Round 2 & 3 = supply/demand (maybe manually input)
    
    # Timer Configuration
    PARTICIPANT_JOIN_TIMEOUT = 20  # 20 seconds - after this time, participant joining is automatically closed

# --------------------------------------------------------------------
# Models
# --------------------------------------------------------------------
class Subsession(BaseSubsession):
    participant_joining_closed = models.BooleanField(initial=False)
    session_start_seconds = models.IntegerField(initial=0)

# Group holds round-specific state for players. (It stores the randomly determined correct investment option for that group in that round)
class Group(BaseGroup):
    successful_option = models.StringField() # The correct investment option for this group in the round
    stock_price = models.CurrencyField()  # Stock price for this round

# Player holds participant-specific state. (It stores each player's investment choice and advisor-following count)
class Player(BasePlayer):

    investment_choice = models.StringField(
        #choices=lambda p: C.CHOICES + ([C.ABSTAIN] if C.ALLOW_ABSTAIN[p.round_number - 1] else []),
        choices=C.CHOICES + [C.ABSTAIN],  # Include all possible choices
        #choices=C.CHOICES,
        widget=widgets.RadioSelect, # Radio buttons for choice selection (Remove this line for dropdown type option)
        )
    is_advisor_followed = models.IntegerField(initial=0)  # counter for how many times the player followed the advisor's suggestion
    advisor_option = models.StringField()  # Store the advisor's suggested option for this player (only visible for admin in Otree)
    can_see_prior = models.BooleanField(initial=False)  # Whether this player can see prior choices in this round (50/50 split across rounds)
    num_prior_choices_seen = models.IntegerField(initial=0) # Number of times prior choices provided to this player across all rounds
    transaction_cost = models.CurrencyField(initial=0)  # Transaction cost for this round
    endowment = models.CurrencyField(initial=0)  # Endowment for this round
    abstained = models.BooleanField(initial=False)  # Whether the player chose to abstain in this round
    # Timer-related fields
    time_elapsed = models.IntegerField(initial=0)  # Time elapsed since session start
    remaining_time = models.IntegerField(initial=20)  # Time remaining
    timer_expired = models.BooleanField(initial=False)  # Whether timer has expired
    session_joined_time = models.IntegerField(initial=0)  # When this player joined the session

# --------------------------------------------------------------------
# Utility Functions
# --------------------------------------------------------------------
# Assign a random successful_option to each group (g) in the subsession
def assign_successful_options(subsession: Subsession):
    for g in subsession.get_groups():
        g.successful_option = random.choices(
            C.CHOICES,
            weights= C.WEIGHTS, # Weighted choice: 45% chance for Option A, 55% chance for Option B
            k=1 # Choose 1 option
        )[0] # random.choices returns a list, so take the first element

# Timer utility functions
def check_timeout_occurred(subsession: Subsession):
    """Check if the participant joining timeout has occurred"""
    import time
    current_time = int(time.time())
    if subsession.session_start_seconds == 0:
        subsession.session_start_seconds = current_time
    elapsed_seconds = current_time - subsession.session_start_seconds
    return elapsed_seconds >= C.PARTICIPANT_JOIN_TIMEOUT

def close_participant_joining_early(subsession: Subsession):
    """Close participant joining and mark subsession as early-formed"""
    subsession.participant_joining_closed = True

def form_groups_with_available_participants(subsession: Subsession):
    """Form groups with available participants when timeout occurs"""
    # Get all participants who have joined
    available_participants = subsession.get_players()
    
    # Form groups - try to make full groups first, then isolated groups
    groups = []
    remaining_participants = list(available_participants)
    
    # Create full groups first
    while len(remaining_participants) >= C.PLAYERS_PER_GROUP:
        group_players = remaining_participants[:C.PLAYERS_PER_GROUP]
        remaining_participants = remaining_participants[C.PLAYERS_PER_GROUP:]
        groups.append(group_players)
    
    # Create isolated group with remaining participants
    if remaining_participants:
        groups.append(remaining_participants)
    
    # Set the group matrix
    subsession.set_group_matrix(groups)

def is_isolated_group(group):
    """Check if a group is isolated (has fewer than PLAYERS_PER_GROUP players)"""
    return len(group.get_players()) < C.PLAYERS_PER_GROUP

def is_active_participant(player):
    """Active means the participant actually entered and made a round-1 decision."""
    return player.in_round(1).field_maybe_none('investment_choice') is not None

def group_by_arrival_time_method(subsession: Subsession, waiting_players):
    """Wait for one shared timer, then group everyone who is currently present."""
    import time
    current_time = int(time.time())

    if subsession.round_number != 1:
        return

    if not waiting_players:
        return

    if subsession.session_start_seconds == 0:
        subsession.session_start_seconds = current_time

    elapsed_seconds = current_time - subsession.session_start_seconds
    if elapsed_seconds < C.PARTICIPANT_JOIN_TIMEOUT:
        return

    subsession.participant_joining_closed = True

    if len(waiting_players) >= C.PLAYERS_PER_GROUP:
        return waiting_players[:C.PLAYERS_PER_GROUP]

    if waiting_players:
        subsession.participant_joining_closed = True
        return waiting_players

# --------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------
# Initial wait page at the start of each round. This page runs at the start of each round to assign successful_option per group
class SetupRoundWaitPage(WaitPage):
    group_by_arrival_time = True

    def is_displayed(self):
        return self.round_number == 1

    def before_all_players_arrive(self):
        assign_successful_options(self.subsession)

    def vars_for_template(self):
        # Calculate timer values directly in vars_for_template
        import time
        current_time = int(time.time())
        
        # Use the one shared timer start set by group_by_arrival_time_method.
        # Fallback only covers the first render before the websocket grouping method runs.
        session_start = self.subsession.session_start_seconds or current_time
        if self.subsession.session_start_seconds == 0:
            self.subsession.session_start_seconds = session_start

        time_elapsed = current_time - session_start
        
        # Calculate remaining time
        remaining_time = C.PARTICIPANT_JOIN_TIMEOUT - time_elapsed
        if remaining_time < 0:
            remaining_time = 0
        
        # Set timer_expired flag
        timer_expired = remaining_time <= 0
        
        # Store values in player model (these will be saved automatically)
        self.time_elapsed = time_elapsed
        self.remaining_time = remaining_time
        self.timer_expired = timer_expired

        if self.session_joined_time == 0:
            self.session_joined_time = current_time

        if timer_expired and not self.subsession.participant_joining_closed:
            self.subsession.participant_joining_closed = True
        
        return {
            'time_elapsed': time_elapsed,
            'remaining_time': remaining_time,
            'timer_expired': timer_expired,
            'participant_join_timeout': C.PARTICIPANT_JOIN_TIMEOUT,
        }

    # Assign successful_option to group when all players arrive (function is in utility section)
    def after_all_players_arrive(self):
        assign_successful_options(self.subsession) # Used subsession here to assign successful options for all groups in the subsession.

# Introduction page (description of the experiment) shown only in the first round - Check HTML template for content
class Introduction(Page):
    def is_displayed(self):
        return self.round_number == 1
    
    def vars_for_template(self):
        return {
            'endowment_round1': C.ENDOWMENT[0],
            'endowment_round2': C.ENDOWMENT[1],
            'endowment_round3': C.ENDOWMENT[2],
            'stock_price_round1': C.STOCK_PRICES[0],
            'transaction_cost_round1': C.TRANSACTION_COSTS[0],
            'transaction_cost_round2': C.TRANSACTION_COSTS[1],
            'transaction_cost_round3_optionA': C.TRANSACTION_COSTS[2][0],
            'transaction_cost_round3_optionB': C.TRANSACTION_COSTS[2][1],
        }

# Wait page to ensure sequential decision making by players in a group
class SequentialWaitPage(Page): # Tried making it a WaitPage but it didn't work as intended because WaitPage waits for all players in a group/subsession etc.
    # Wait so player decisions are sequential by id_in_group. Player with id_in_group=1 decides first, then id_in_group=2, etc.
    # Player id can change each round due to constant shuffling each round, so this ensures correct order remains each round.
    def is_displayed(self):
        if self.round_number > 1 and self.in_round(1).field_maybe_none('investment_choice') is None:
            return False
        if self.id_in_group == 1: # First player in group can proceed without waiting
            return False
        for p in self.group.get_players(): # Each players wait until all prior players have made their decisions
            if p.id_in_group < self.id_in_group and p.field_maybe_none('investment_choice') is None:
                return True
        return False

# Decision page where players make their investment choices
class Decision(Page):
    form_model = 'player' # Binds the form to the Player model
    form_fields = ['investment_choice'] # Field where player selects their investment option (created in Player model)

    # Decision page is displayed only when it's the player's turn to decide (sequentially by id_in_group)
    def is_displayed(self):
        if self.round_number > 1 and self.in_round(1).field_maybe_none('investment_choice') is None:
            return False
        if self.id_in_group == 1: # First player in group can always see the decision page (no waiting needed)
            return True
        for p in self.group.get_players():
            if p.id_in_group < self.id_in_group and p.field_maybe_none('investment_choice') is None:
                return False
        return True

    # Variables for the decision page template
    def vars_for_template(self):
        # First player has no prior choices to see, so always False for them
        if self.id_in_group == 1:
            can_see_prior = False
            prior_choices = []
            num_prior_seen = 0
        else:
            # 50/50 split: Player can see prior choices if their position in group is odd/even based on round
            # This creates alternating pattern across rounds for each player and also mix the prior decision visibility within a group
            can_see_prior = (self.id_in_group % 2 == self.round_number % 2)
        
            num_prior_seen = 0
            prior_choices = []
            if can_see_prior:
                # First try within group
                prior_choices = [
                    p.field_maybe_none('investment_choice')
                    for p in self.group.get_players()
                    if p.id_in_group < self.id_in_group and p.field_maybe_none('investment_choice') is not None
                ]
                num_prior_seen = len(prior_choices)
                
                # If we need more choices and this is an isolated group, look at other groups
                if is_isolated_group(self.group) and len(prior_choices) < min(2, self.id_in_group - 1):
                    other_groups = [g for g in self.subsession.get_groups() if g != self.group]
                    for other_group in other_groups:
                        other_choices = [
                            p.field_maybe_none('investment_choice')
                            for p in other_group.get_players()
                            if p.field_maybe_none('investment_choice') is not None
                        ]
                        prior_choices.extend(other_choices[:2])  # Add up to 2 choices from each group
                        if len(prior_choices) >= min(2, self.id_in_group - 1):
                            break
                
                # Limit to maximum reasonable number of prior choices
                prior_choices = prior_choices[:min(2, self.id_in_group - 1)]
                num_prior_seen = len(prior_choices)

        # Store these values for saving in before_next_page
        self.participant.vars['temp_can_see_prior'] = can_see_prior
        self.participant.vars['temp_num_prior_seen'] = num_prior_seen
        
        allow_abstain = C.ALLOW_ABSTAIN[self.round_number - 1] # Check if abstain option is allowed in this round

        # Advisor logic (Advisor can give different advice for each player in a group - meaning advisor's suggestions is not group-wide)
        #advisor_message = None # (for future use if needed when advisor message is not always given - check decision.html)
        random_value_percent = random.random() * 100 # Random value between 0-100
        # Determine advisor's suggested option based on the random value and threshold
        # Use safe access for successful_option; isolated groups may not have one yet
        successful = self.group.field_maybe_none('successful_option')
        if random_value_percent < C.ADVISOR_CORRECTION_THRESHOLD_PERCENT:
            advisor_option = successful if successful is not None else random.choice(C.CHOICES)
        else:
            # If successful is None, treat all choices as possible "wrong" options
            base_choices = C.CHOICES if successful is None else [opt for opt in C.CHOICES if opt != successful]
            advisor_option = random.choice(base_choices)

        advisor_message = f"Option {advisor_option}" # Advisor's recommendation message - check decision.html for display
        self.advisor_option = advisor_option # Save the advisor_option into player model so it persists for future reference (like results page)

        return {
            'stock_price': C.STOCK_PRICES[self.round_number - 1],
            'prior_choices': prior_choices,
            'is_first_player': self.id_in_group == 1,
            #'advisor_option': advisor_option,
            'advisor_message': advisor_message,
            'can_see_prior': can_see_prior,
            'num_prior_choices_seen': num_prior_seen,
            'allow_abstain': allow_abstain,
        }

    def before_next_page(player, timeout_happened):
        player.can_see_prior = player.participant.vars.get('temp_can_see_prior', False)
        player.num_prior_choices_seen = player.participant.vars.get('temp_num_prior_seen', 0)

# Wait page to ensure all players have made their decisions before calculating results
class ResultsWaitPage(WaitPage):
    def is_displayed(self):
        return is_active_participant(self)

    # After all players arrive, calculate payoffs based on their investment choices
    def after_all_players_arrive(group: Group):
        """Calculate payoffs for all players in the group.
        Handles abstention, safe access to ``successful_option`` for isolated groups,
        applies round‑specific transaction costs, and updates advisor follow‑up counts.
        """
        for p in group.get_players():
            if not is_active_participant(p):
                continue

            # Abstention handling
            if p.investment_choice == C.ABSTAIN:
                p.abstained = True
                p.payoff = cu(0)
                continue

            p.abstained = False

            # Determine base payoff using safe access to successful_option
            successful = group.field_maybe_none('successful_option')
            if successful is not None and p.investment_choice == successful:
                base_payoff = C.CORRECT_CHOICE_REWARD
            else:
                base_payoff = -C.INCORRECT_CHOICE_PENALTY

            # Round‑specific transaction costs
            round_num = group.subsession.round_number
            if round_num == 1:
                transaction_cost = C.TRANSACTION_COSTS[0]
            elif round_num == 2:
                transaction_cost = C.TRANSACTION_COSTS[1]
            elif round_num == 3:
                if p.investment_choice == C.OPTION_A:
                    transaction_cost = C.TRANSACTION_COSTS[2][0]
                else:
                    transaction_cost = C.TRANSACTION_COSTS[2][1]
            else:
                transaction_cost = cu(0)

            # Set endowment and stock price for the round
            p.endowment = C.ENDOWMENT[round_num - 1]
            group.stock_price = C.STOCK_PRICES[round_num - 1]
            p.transaction_cost = transaction_cost
            p.payoff = base_payoff + p.endowment - transaction_cost - group.stock_price

            # Update advisor follow‑up count
            if p.investment_choice == p.advisor_option:
                p.is_advisor_followed += 1

# Results page showing round results to players
class RoundResults(Page):
    def is_displayed(self):
        return is_active_participant(self)

    def vars_for_template(self):
        successful = self.group.field_maybe_none('successful_option')
        player_choice = self.investment_choice
        is_correct = (successful == player_choice)
        return {
            'successful_option': successful,
            'player_choice': player_choice,
            'is_correct': is_correct,
            'base_payoff': C.CORRECT_CHOICE_REWARD if is_correct else -C.INCORRECT_CHOICE_PENALTY,
            'round_payoff': self.payoff,
            'total_payoff': sum(p.payoff for p in self.in_all_rounds()),
            'transaction_cost': self.transaction_cost,
            'advisor_option': self.advisor_option,
            'total_followed_adviser': sum(p.is_advisor_followed for p in self.in_all_rounds()),
            'endowment_round': self.endowment,
        }

# Wait page that redistributes players into new groups after each round

# To achieve randomness and after reading many posts i selected Round robin assignment method for it
# how it works:
# Each player moves to a new group based on their position in the current group on first come first serve basis.
# For example, in a 3-group setup with 3 players each: 
# Group 1: P1, P2, P3
# Group 2: P4, P5, P6
# Group 3: P7, P8, P9
# After redistribution:
# P1 goes to Group 2, P2 goes to Group 3, P3 goes to Group 1
# P4 goes to Group 3, P5 goes to Group 1, P6 goes to Group 2
# P7 goes to Group 1, P8 goes to Group 2, P9 goes to Group 3
# whereas position in a group is determined by id_in_group (1,2,3,...)
# so it will be like
# Group 1: P3, P6, P9
# Group 2: P1, P4, P7
# Group 3: P2, P5, P8
# Think in matrix form it will be easier to understand (it is just transpose + shift by 1):
# Current Matrix (Round N):
# | G1 | G2 | G3 |
# |----|----|----|
# | P1 | P4 | P7 |  --> Players with id_in_group=1
# | P2 | P5 | P8 |  --> Players with id_in_group=2   
# | P3 | P6 | P9 |  --> Players with id_in_group=3
# After Redistribution (Round N+1):
# | G1 | G2 | G3 |
# |----|----|----|
# | P3 | P1 | P2 |  --> Players with id_in_group=1
# | P6 | P4 | P5 |  --> Players with id_in_group=2
# | P9 | P7 | P8 |  --> Players with id_in_group=3

# This continues for each round until the final round is reached.

class RedistributeGroupsWaitPage(WaitPage):
    wait_for_all_groups = False

    def is_displayed(self):
        return self.round_number < C.NUM_ROUNDS and is_active_participant(self) # Only before the last round since no redistribution needed after last round

    def after_all_players_arrive(self):
        next_sub = self.subsession.in_round(self.round_number + 1)

        current_matrix = []
        for group in self.subsession.get_groups():
            actual_group_players = [
                p for p in group.get_players()
                if p.field_maybe_none('investment_choice') is not None
            ]
            if actual_group_players:
                current_matrix.append(actual_group_players)

        actual_num_groups = len(current_matrix)

        if actual_num_groups == 0:
            return

        next_players_by_participant = {p.participant: p for p in next_sub.get_players()}
        active_participants = {p.participant for group_players in current_matrix for p in group_players}
        absent_next_players = [
            p for p in next_sub.get_players()
            if p.participant not in active_participants
        ]

        first_actual_group_id = min(group_players[0].group.id_in_subsession for group_players in current_matrix)

        # Only one actual group should perform the redistribution. Other groups just wait at group level
        # and then continue, so absent session participants are not required.
        if self.group.id_in_subsession != first_actual_group_id:
            return

        # Skip redistribution for isolated groups
        active_players = [p for group_players in current_matrix for p in group_players]
        active_count = len(active_players)

        if any(len(group_players) < C.PLAYERS_PER_GROUP for group_players in current_matrix):
            # Keep current grouping for isolated groups (no reshuffling)
            next_matrix = [
                [next_players_by_participant[p.participant] for p in group_players]
                for group_players in current_matrix
            ]
            # Add singleton groups for participants that did not join this round
            next_matrix.extend([[p] for p in absent_next_players])
            # Filter out any empty groups that may appear (e.g., groups with no players after a dropout)
            cleaned_matrix = [g for g in next_matrix if g]
            # Convert player objects to their id_in_subsession for oTree's set_group_matrix
            id_matrix = [[p.id_in_subsession for p in group] for group in cleaned_matrix]
            # Ensure the matrix has a contiguous set of group IDs by padding with empty lists if needed
            expected_groups = max(len(id_matrix), math.ceil(active_count / C.PLAYERS_PER_GROUP))
            while len(id_matrix) < expected_groups:
                id_matrix.append([])
            next_sub.set_group_matrix(id_matrix)
            assign_successful_options(next_sub)
        else:
            # Normal redistribution: create the minimal number of groups needed (max size C.PLAYERS_PER_GROUP)
            num_groups = max(1, math.ceil(active_count / C.PLAYERS_PER_GROUP))
            # Build a temporary matrix of player objects for active participants
            temp_matrix = [[] for _ in range(num_groups)]
            for idx, player in enumerate(active_players):
                target_group_index = idx % num_groups
                temp_matrix[target_group_index].append(next_players_by_participant[player.participant])
            # Add singleton groups for participants that did not join this round
            for p in absent_next_players:
                temp_matrix.append([p])
            # Convert to matrix of player IDs as required by oTree
            id_matrix = [[p.id_in_subsession for p in group] for group in temp_matrix]
            # Ensure the matrix has a contiguous set of group IDs by padding with empty lists if needed
            expected_groups = max(len(id_matrix), math.ceil(active_count / C.PLAYERS_PER_GROUP))
            while len(id_matrix) < expected_groups:
                id_matrix.append([])
            next_sub.set_group_matrix(id_matrix)
            assign_successful_options(next_sub)
    def vars_for_template(self):
        num_groups = 0
        for group in self.subsession.get_groups():
            actual_group_players = [
                p for p in group.get_players()
                if p.field_maybe_none('investment_choice') is not None
            ]
            if actual_group_players:
                num_groups += 1
        return {
            'next_round': self.subsession.round_number+1,
            'num_groups': num_groups,
        }
# Final results page shown only at the end of the last round
class FinalResults(Page):
    def is_displayed(self):
        return self.round_number == C.NUM_ROUNDS and is_active_participant(self)
    def vars_for_template(self):
        # currently displaying total payoff and total times advisor was followed (can add more if needed)
        return {
            'total_payoff': sum(p.payoff for p in self.in_all_rounds()), # Total payoff across all rounds
            'total_followed_adviser': sum(p.is_advisor_followed for p in self.in_all_rounds()) # Total times advisor was followed across all rounds
        }

# Page sequence
page_sequence = [
    SetupRoundWaitPage,  # Ensures successful_option is set before decisions
    Introduction, # shown only in round 1
    SequentialWaitPage, # Ensures sequential decision making
    Decision, # Investment decision page
    ResultsWaitPage, # Calculate payoffs after all decisions by all players
    RoundResults, # Show round results
    RedistributeGroupsWaitPage, # Redistribute players into new groups after each round
    FinalResults, # Show final results at the end of last round
]

# Custom CSV export for the 'social_investment' app. 
# Exports only participants from the most recent session using this app.
# Otree auto generated csv file mixes data from multiple sessions with strange outputs.

def custom_export(players):

    if not players:
        return  # no data at all to export

    # Filter players to the latest session (in debug mode i saw data from multiple sessions getting mixed)
    # Each Player has .session.code (unique strings for that session only)
    # This filtering can be removed if you want data from all sessions 
    # (i highly dont recommend it be removed). If u do you need to execute resetdb command before each new session to avoid mixing data.
    
    # Find the latest session code by looking for the maximum internal session id
    # We use key=lambda p: p.session.id to find the player in the most recent session
    latest_player = max(players, key=lambda p: p.session.id)
    latest_session_code = latest_player.session.code
    # Filter the list to only include players from that specific session
    players = [p for p in players if p.session.code == latest_session_code]

    # Group players by participant unique code (e.g. qb9hcpdd). Participant is above Player in hierarchy. so a single participant has multiple players (one per round) across rounds.
    participants = {} # dictionary to hold participant code as key and list of their players as value
    for p in players:
        part_code = p.participant.code
        participants.setdefault(part_code, []).append(p)
    # Experiment settings:
    # Here we are getting row wise data for each experimental setting used in the experiment. just once at the top of the CSV file.
    yield ['EXPERIMENT SETTINGS (Session: %s)' % latest_session_code]
    yield ['PLAYERS_PER_GROUP', C.PLAYERS_PER_GROUP]
    total_players = len(participants)  # Total unique participants
    calculated_num_groups = total_players // C.PLAYERS_PER_GROUP
    yield ['NUM_GROUPS', calculated_num_groups] # Calculated number of groups based on unique participants and players per group (constant doesnt work since we specify number in otree site)
    yield ['NUM_ROUNDS', C.NUM_ROUNDS]
    yield ['CORRECT_CHOICE_REWARD', C.CORRECT_CHOICE_REWARD]
    yield ['INCORRECT_CHOICE_PENALTY', C.INCORRECT_CHOICE_PENALTY]
    #yield ['TRANSACTION_COST', C.TRANSACTION_COST] # Removed as transaction cost is now round specific
    yield ['ADVISOR_CORRECTION_THRESHOLD_PERCENT', C.ADVISOR_CORRECTION_THRESHOLD_PERCENT]
    yield [] # Empty row for separation

    # Participant data headers:
    # Here we are getting column wise data for each participant across all rounds below the experiment settings data in the CSV file.
    
    # Section 1 - Round Based Monitoring with Prior Choice Visibility Monitoring
    yield ['ROUND BASED MONITORING']
    yield [
        'Round',
        'Participant',
        'Group_Number',
        'Position_In_Group',
        'Group_Size',
        'Is_Isolated_Group',
        'Saw_Prior_Choices',
        'Num_Choices_Seen',
        'Followed_Advisor',
        'Player_Choice',
        'Was_Correct',
        ]
    
    sorted_players = sorted(players, key=lambda p: (p.round_number, p.participant.code))
    #sorted_players = sorted(players, key=lambda p: (p.round_number, p.group.id_in_subsession, p.id_in_group))
    
    for p in sorted_players:
        was_correct = ''
        if p.group and p.group.field_maybe_none('successful_option') and p.investment_choice:
            was_correct = 'Yes' if p.investment_choice == p.group.successful_option else 'No'
        followed_advisor = ''
        if p.investment_choice and p.advisor_option:
            followed_advisor = 'Yes' if p.investment_choice == p.advisor_option else 'No'
        # Calculate group size and isolated group status
        group_size = len(p.group.get_players()) if p.group else 0
        is_isolated = 'Yes' if p.group and is_isolated_group(p.group) else 'No'
        
        yield [
            p.round_number,
            p.participant.code,
            p.group.id_in_subsession,
            p.id_in_group,
            group_size,
            is_isolated,
            'Yes' if p.can_see_prior else 'No',
            p.num_prior_choices_seen,
            followed_advisor,
            p.investment_choice or '',
            was_correct
        ]
    
    yield []

    # Section 2 - Participant Summary
    yield ['PARTICIPANT SUMMARY']

    yield [
        'ID',
        'participant_code',
        'num_correct',
        'num_incorrect',
        'times_followed_adviser',
        'total_payoff',
    ]

    # Participant rows
    # For each participant, calculate their total correct/incorrect choices, times followed adviser, and total payoff across all rounds
    for idx, (part_code, part_players) in enumerate(participants.items(), start=1): # Unique index (idx) for each participant row
        custom_id = f'P{idx}' # Custom ID for participant (idx= 1 -> P1, idx = 2 -> P2, etc.)

        # Summing participant successful choices across all rounds (for each player)
        # Example:
        # Example for P1:
        # Round 1 → choice matches group’s successful_option → count = 1.
        # Round 2 → incorrect → count stays 1.
        # Round 3 → incorrect → count stays 1.
        # So num_correct = 1.

        num_correct = sum(
            1 for pp in part_players
            # There are extra conditions here to avoid AttributeError that i faced earlier. I am scared to remove them now.
            # No investment choice yet and No group assigned yet (both should not happen in normal flow but just in case)
            # Similar case with maybe_none method used in group to avoid errors.
            # In case anything fails at least that participant will have empty row instead of crashing the export function.
            if pp.investment_choice 
            and pp.group
            and pp.group.field_maybe_none('successful_option') == pp.investment_choice
        )

        num_incorrect = C.NUM_ROUNDS - num_correct # Total incorrect choice is simply total rounds - correct choices
        times_followed_adviser = sum(pp.is_advisor_followed or 0 for pp in part_players) # Sum of times adviser was followed across all rounds
        total_payoff = sum(pp.payoff or 0 for pp in part_players) # Total payoff across all rounds
        
        yield [
            custom_id,
            part_code,
            num_correct,
            num_incorrect,
            times_followed_adviser,
            float(total_payoff),
        ]

