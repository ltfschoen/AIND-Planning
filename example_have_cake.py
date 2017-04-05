# Import from Logic the following:
#
#   - Expr class - Expressions allowed to be represented as say E
#                  maths expressions using symbols
#                  with where E.op and E.args is its operator and arguments
#                  to form logical sentences.
#                  Represent as either `~(P & Q)  |'==>'|  (~P | ~Q)` or
#                  with expr shortcut `expr('~(P & Q)  ==>  (~P | ~Q)')`
#
#   - PropKB class - Propositional Knowledge Bases used to
#                  represent a knowledge base (KB) of propositional local sentences.
#                  using its four methods
#                    - __init__(self, sentence=None) - create clauses field as
#                      list of all sentences in knowledge database where each
#                      sentence comprises just literals and ORs
#                    - tell(self, sentence) - adds a sentence to the KB by
#                      converting to Conjunctive Normal Form (CNF), extracting
#                      all clauses to clauses field
#                    - ask_generator(self, query) - returns all substitutions
#                      that make query True (i.e. returns {...} or False).
#                    - ask_if_true(self, query) - same as ask_generator
#                      but returns True or False
#                    - retract(self, sentence) - converts sentences to clauses
#                      and then removes all clauses from the knowledge base
from aimacode.logic import PropKB

# Import from Action the following:
#
#   - Action class - Action Schema used to describe Actions using the
#                  Expr class including Preconditions and Effects
#                  where Variables are args using the
#                  Planning Planning Domain Definition Language (PDDL)
from aimacode.planning import Action

from aimacode.search import (
    Node,
    breadth_first_search,
    astar_search,
    depth_first_graph_search,
    uniform_cost_search,
    greedy_best_first_graph_search,
    Problem,
)
from aimacode.utils import expr
from lp_utils import (
    FluentState,
    encode_state,
    decode_state
)

# Import from PlanningGraph the following:
#
#  - PgNode class - Planning Graph Nodes base class including:
#
#                       Properties:
#                           - Parent - set of parent nodes up a level
#                           - Child - set of child nodes down a level
#                           - Mutex - set of sibling nodes mutually exclusive with current node
#
#  - PgNode_s class - Planning Graph "State" (Literal Fluent) Nodes:
#    (inherits from PgNode)
#
#                       Properties:
#                           - Parent - set of parent nodes up at previous Action level (A-level)
#                           - Child - set of child nodes down at next Action level (A-Level)
#                           - Mutex - set of sibling State Nodes (S-Nodes) mutex with current node
#
#  - PgNode_a class - Planning Graph "Action" (Type Nodes):
#    (inherits from PgNode)
#
#                       Properties:
#                           - Parent - set of parent Precondition nodes up at previous State level (S-level)
#                           - Child - set of child Effect nodes down at next State level (S-level)
#                           - Mutex - set of sibling Action Nodes (A-Nodes) mutex with current node
#
#  - PlanningGraph class - Planning Graph is built with alternating Action and State levels until the
#                           last two State levels contain the same literals
#
#                       Properties:
#                           - Problem - i.e. subclass of HaveCakeProblem
#                           - Serial Planning - Whether one Action may occur at a time
#                           - Fluent State - fluent states T/F (i.e. string in form 'TFTTFF')
#                           - Ground Actions - list of valid ground actions and noop actions
#                               - Noop Actions lists comprise both a positive no-op action
#                               (literal as positive precondition with literal expression added as output
#                               effect) and negative no-op action (literal as negative precondition with
#                               literal expression removed from output effect) for each literal expression that
#                               they pass through levels of planning graph.
#                           - State Levels - list of sets of PgNode_s that each represent an S-level
#                           - Action Levels - list of sets of PgNode_a that each represent an A-level
#
#                        Functions:
#
#                           - Noop Actions
#                           - Planning Graph - create
#                           - Action - add A-level to Planning Graph
#                           - State - add S-level (literal) to Planning Graph
#                           - Mutex - update A-level node mutex for siblings when
#                               - Serial Planning Graph
#                               - Action node pairs are non-persistence actions
#                               - Action node pairs have either Inconsistent Effects, Interference, Competing needs

from my_planning_graph import PlanningGraph
from run_search import run_search

import my_logging
from my_logging import *
my_logging.setup_log_level()

class HaveCakeProblem(Problem):
    def __init__(self, initial: FluentState, goal: list):
        self.state_map = initial.pos + initial.neg
        Problem.__init__(self, encode_state(initial, self.state_map), goal=goal)
        self.actions_list = self.get_actions()

    # Returns list including Eat Action and Bake Action
    def get_actions(self):
        precond_pos = [expr("Have(Cake)")]
        precond_neg = []
        effect_add = [expr("Eaten(Cake)")]
        effect_rem = [expr("Have(Cake)")]
        eat_action = Action(expr("Eat(Cake)"),
                            [precond_pos, precond_neg],
                            [effect_add, effect_rem])
        precond_pos = []
        precond_neg = [expr("Have(Cake)")]
        effect_add = [expr("Have(Cake)")]
        effect_rem = []
        bake_action = Action(expr("Bake(Cake)"),
                             [precond_pos, precond_neg],
                             [effect_add, effect_rem])
        return [eat_action, bake_action]

    def actions(self, state: str) -> list:  # of Action
        possible_actions = []
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        for action in self.actions_list:
            is_possible = True
            for clause in action.precond_pos:
                if clause not in kb.clauses:
                    is_possible = False
            for clause in action.precond_neg:
                if clause in kb.clauses:
                    is_possible = False
            if is_possible:
                possible_actions.append(action)
        return possible_actions

    def result(self, state: str, action: Action):
        new_state = FluentState([], [])
        old_state = decode_state(state, self.state_map)
        for fluent in old_state.pos:
            if fluent not in action.effect_rem:
                new_state.pos.append(fluent)
        for fluent in action.effect_add:
            if fluent not in new_state.pos:
                new_state.pos.append(fluent)
        for fluent in old_state.neg:
            if fluent not in action.effect_add:
                new_state.neg.append(fluent)
        for fluent in action.effect_rem:
            if fluent not in new_state.neg:
                new_state.neg.append(fluent)
        return encode_state(new_state, self.state_map)

    def goal_test(self, state: str) -> bool:
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                return False
        return True

    def h_1(self, node: Node):
        # note that this is not a true heuristic
        h_const = 1
        return h_const

    def h_pg_levelsum(self, node: Node):
        # uses the planning graph level-sum heuristic calculated
        # from this node to the goal
        # requires implementation in PlanningGraph
        pg = PlanningGraph(self, node.state)
        pg_levelsum = pg.h_levelsum()
        return pg_levelsum

    def h_ignore_preconditions(self, node: Node):
        count = 0
        kb = PropKB()
        kb.tell(decode_state(node.state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                count += 1
        return count


def have_cake():
    def get_init():
        pos = [expr('Have(Cake)'),
               ]
        neg = [expr('Eaten(Cake)'),
               ]
        return FluentState(pos, neg)

    def get_goal():
        return [expr('Have(Cake)'),
                expr('Eaten(Cake)'),
                ]

    return HaveCakeProblem(get_init(), get_goal())


if __name__ == '__main__':
    p = have_cake()
    print("**** Have Cake example problem setup ****")
    print("Initial state for this problem is {}".format(p.initial))
    print("Actions for this domain are:")
    for a in p.actions_list:
        print('   {}{}'.format(a.name, a.args))
    print("Fluents in this problem are:")
    for f in p.state_map:
        print('   {}'.format(f))
    print("Goal requirement for this problem are:")
    for g in p.goal:
        print('   {}'.format(g))
    print()
    print("*** Breadth First Search")
    run_search(p, breadth_first_search)
    print("*** Depth First Search")
    run_search(p, depth_first_graph_search)
    print("*** Uniform Cost Search")
    run_search(p, uniform_cost_search)
    print("*** Greedy Best First Graph Search - null heuristic")
    run_search(p, greedy_best_first_graph_search, parameter=p.h_1)
    print("*** A-star null heuristic")
    run_search(p, astar_search, p.h_1)
    print("*** A-star ignore preconditions heuristic")
    run_search(p, astar_search, p.h_ignore_preconditions)
    print("*** A-star levelsum heuristic")
    run_search(p, astar_search, p.h_pg_levelsum)
