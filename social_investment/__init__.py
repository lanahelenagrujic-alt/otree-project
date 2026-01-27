from otree.api import * # oTree imports
import random # for random choice and advisor probability


doc = """
Financial Decision Experiment:

Overview:
Participants are organized into multiple groups per round, with each group containing 
a fixed number of players (PLAYERS_PER_GROUP). Each group receives one randomly 
determined 'successful' investment option (either Option A or Option B).

Sequence per Round:
1. Groups are formed at the start of each round (players are grouped randomly).
2. Within each group, players make their investment choices sequentially, one after another.
3. An advisor gives each player a recommendation, which may be correct or incorrect, based 
   on a predefined probability threshold (ADVISOR_CORRECTION_THRESHOLD_PERCENT).
4. Payoffs are calculated as: correct choices earn a reward, incorrect choices earn no reward 
   or a penalty (if defined) and transaction costs are deducted from all payoffs.

Group Redistribution:
- At the end of every round except the last, players are redistributed cyclically:
  the position of a player within their group is used to determine which group they join next.
- This guarantees players interact with different group members across rounds, 
  promoting randomness to the experiment.

End of Experiment:
- After the final round, total payoff and total times the advisor was followed 
  are shown to each participant.
"""

# --------------------------------------------------------------------
# Constants - Experiment Configuration
# --------------------------------------------------------------------
class C(BaseConstants):
    NAME_IN_URL = 'social_investment' # URL name for the app (u can change it to display different name in URL)
    PLAYERS_PER_GROUP = 3 # Number of players/participants per group
    NUM_GROUPS = 3 # Number of groups per round
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

# --------------------------------------------------------------------
# Models
# --------------------------------------------------------------------
class Subsession(BaseSubsession):
    pass

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
    can_see_prior = models.BooleanField()  # Whether this player can see prior choices in this round (50/50 split across rounds)
    transaction_cost = models.CurrencyField(initial=0)  # Transaction cost for this round
    endowment = models.CurrencyField(initial=0)  # Endowment for this round
    abstained = models.BooleanField(initial=False)  # Whether the player chose to abstain in this round

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

# --------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------
# Initial wait page at the start of each round. This page runs at the start of each round to assign successful_option per group
class SetupRoundWaitPage(WaitPage):
    wait_for_all_groups = True # Wait for all groups to be ready before proceeding

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
        if self.id_in_group == 1: # First player in group can always see the decision page (no waiting needed)
            return True
        for p in self.group.get_players():
            if p.id_in_group < self.id_in_group and p.field_maybe_none('investment_choice') is None:
                return False
        return True
    
    """ 
    #DEL BEFORE DEPLOYMENT:
    # problem with dynamic choices in oTree form fields - need to research more. also cant access the subsession or group from here directly
    # Define choices dynamically based on round
    def investment_choice_choices(self):
        if (C.ALLOW_ABSTAIN[Subsession.round_number-1]):  # Check if abstain option is allowed
            choices_option = C.CHOICES + [C.ABSTAIN]  # Include abstain option for choice field
        else :
            choices_option = C.CHOICES  # Only include standard choices
    """

    # Variables for the decision page template
    def vars_for_template(self):
        # 50/50 split: Player can see prior choices if their position in group is odd/even based on round
        # This creates alternating pattern across rounds for each player and also mix the prior decision visibility within a group
        self.can_see_prior = (self.id_in_group % 2 == self.round_number % 2)
        
        prior_choices = []
        if self.can_see_prior:
            prior_choices = [
                p.field_maybe_none('investment_choice')
                for p in self.group.get_players()
                if p.id_in_group < self.id_in_group and p.field_maybe_none('investment_choice') is not None
            ]
        
        allow_abstain = C.ALLOW_ABSTAIN[self.round_number - 1] # Check if abstain option is allowed in this round

        # Advisor logic (Advisor can give different advice for each player in a group - meaning advisor's suggestions is not group-wide)
        #advisor_message = None # (for future use if needed when advisor message is not always given - check decision.html)
        random_value_percent = random.random() * 100 # Random value between 0-100
        # Determine advisor's suggested option based on the random value and threshold
        if random_value_percent < C.ADVISOR_CORRECTION_THRESHOLD_PERCENT:
            advisor_option = self.group.successful_option
        else:
            wrong_options = [opt for opt in C.CHOICES if opt != self.group.successful_option]
            advisor_option = random.choice(wrong_options)

        advisor_message = f"Option {advisor_option}" # Advisor's recommendation message - check decision.html for display
        self.advisor_option = advisor_option # Save the advisor_option into player model so it persists for future reference (like results page)

        return {
            'stock_price': C.STOCK_PRICES[self.round_number - 1],
            'prior_choices': prior_choices,
            'is_first_player': self.id_in_group == 1,
            #'advisor_option': advisor_option,
            'advisor_message': advisor_message,
            'can_see_prior': self.can_see_prior,
            'allow_abstain': allow_abstain,
        }

# Wait page to ensure all players have made their decisions before calculating results
class ResultsWaitPage(WaitPage):
    # After all players arrive, calculate payoffs based on their investment choices
    def after_all_players_arrive(group: Group):
        for p in group.get_players():
            # Check if player chose to abstain
            if p.investment_choice == C.ABSTAIN:
                p.abstained = True
                # No penalty or transaction cost for abstaining but also no endowments
                p.payoff = cu(0)

            else:
                p.abstained = False
                # Calculate base payoff for normal choices
                if p.investment_choice == group.successful_option:
                    base_payoff = C.CORRECT_CHOICE_REWARD
                else:
                    base_payoff = -C.INCORRECT_CHOICE_PENALTY
            
                # Apply round-specific transaction costs using TRANSACTION_COSTS constant
                if group.subsession.round_number == 1:
                    transaction_cost = C.TRANSACTION_COSTS[0]  # = cu(0)
                elif group.subsession.round_number == 2:
                    transaction_cost = C.TRANSACTION_COSTS[1]  # = cu(0)
                    # All choices pay same cost: cu(0)
                elif group.subsession.round_number == 3:
                    # Round 3: Different costs for A and B
                    if p.investment_choice == C.OPTION_A:
                        transaction_cost = C.TRANSACTION_COSTS[2][0]  # cu(0.1)
                    else:
                        transaction_cost = C.TRANSACTION_COSTS[2][1]  # cu(0.5)
                else: # default case (should not occur)
                    transaction_cost = cu(0)
                
                p.endowment = C.ENDOWMENT[group.subsession.round_number-1]  # Set endowment for this round
                group.stock_price = C.STOCK_PRICES[group.subsession.round_number-1]  # Set stock price for this round
                p.transaction_cost = transaction_cost
                p.payoff = base_payoff + p.endowment - transaction_cost - group.stock_price
            
            # Update advisor suggestion following counter
            if p.investment_choice == p.advisor_option:
                p.is_advisor_followed += 1

# Results page showing round results to players
class RoundResults(Page):
    def vars_for_template(self):
        successful = self.group.successful_option
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
    wait_for_all_groups = True

    def is_displayed(self):
        return self.round_number < C.NUM_ROUNDS # Only before the last round since no redistribution needed after last round

    def after_all_players_arrive(self):
        current_matrix = self.subsession.get_group_matrix()
        num_groups = len(current_matrix)
        new_matrix = [[] for _ in range(num_groups)] # Initialize empty list for new groups (lists within a list because get_group_matrix returns a list of lists)

        for g_index, group_players in enumerate(current_matrix):
            for p_index, player in enumerate(group_players):
                # Create new group using round robin assignment logic:
                # Shifts players into different groups based on both their original group number and their position within that group.
                # Also wraps around so if the index goes beyond the last group, it restarts at group 0.
                target_group_index = (g_index + p_index + 1) % num_groups
                new_matrix[target_group_index].append(player) # Append player to the new target group
        
        # Set the new grouping (group matrix) we created above for the next round
        next_sub = self.subsession.in_round(self.round_number + 1)
        next_sub.set_group_matrix(new_matrix)

        # Assign successful_option for new groups after redistribution using utility function
        assign_successful_options(next_sub)
    def vars_for_template(self):
        # currently displaying total payoff and total times advisor was followed (can add more if needed)
        return {
            'next_round': self.subsession.round_number+1,
        }
# Final results page shown only at the end of the last round
class FinalResults(Page):
    def is_displayed(self):
        return self.round_number == C.NUM_ROUNDS
    def vars_for_template(self):
        # currently displaying total payoff and total times advisor was followed (can add more if needed)
        return {
            'total_payoff': sum(p.payoff for p in self.in_all_rounds()), # Total payoff across all rounds
            'total_followed_adviser': sum(p.is_advisor_followed for p in self.in_all_rounds()) # Total times advisor was followed across all rounds
        }

# --------------------------------------------------------------------
# Page sequence
# --------------------------------------------------------------------
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
    yield ['NUM_GROUPS', C.NUM_GROUPS]
    yield ['NUM_ROUNDS', C.NUM_ROUNDS]
    yield ['CORRECT_CHOICE_REWARD', C.CORRECT_CHOICE_REWARD]
    yield ['INCORRECT_CHOICE_PENALTY', C.INCORRECT_CHOICE_PENALTY]
    #yield ['TRANSACTION_COST', C.TRANSACTION_COST] # Removed as transaction cost is now round specific
    yield ['ADVISOR_CORRECTION_THRESHOLD_PERCENT', C.ADVISOR_CORRECTION_THRESHOLD_PERCENT]
    yield [] # Empty row for separation

    # Participant data headers:
    # Here we are getting column wise data for each participant across all rounds below the experiment settings data in the CSV file.
    yield [
        'ID',
        'participant_code',
        'num_correct',
        'num_incorrect',
        'times_followed_adviser',
        'total_payoff'
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
            float(total_payoff)
        ]