from aimacode.logic import PropKB
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
    decode_state,
)
from my_planning_graph import PlanningGraph
# from run_search import run_search

import my_logging
from my_logging import *
my_logging.setup_log_level()


class AirCargoProblem(Problem):
    def __init__(self, cargos, planes, airports, initial: FluentState, goal: list):
        """
        :param cargos: list of str
            cargos in the problem
        :param planes: list of str
            planes in the problem
        :param airports: list of str
            airports in the problem
        :param initial: FluentState object
            positive and negative literal fluents (as expr) describing initial state
        :param goal: list of expr
            literal fluents required for goal test
        """
        self.state_map = initial.pos + initial.neg
        self.initial_state_TF = encode_state(initial, self.state_map)
        Problem.__init__(self, self.initial_state_TF, goal=goal)
        self.cargos = cargos
        self.planes = planes
        self.airports = airports
        self.actions_list = self.get_actions()

    def get_actions(self):
        """ This method creates concrete actions (no variables) for all actions in the problem
        domain action schema and turns them into complete Action objects as defined in the
        aimacode.planning module. It is computationally expensive to call this method directly;
        however, it is called in the constructor and the results cached in the `actions_list` property.

        Returns:
        ----------
        list<Action>
            list of Action objects
        """

        # Create concrete Action objects based on the domain action schema for: Load, Unload, and Fly.
        # Concrete actions definition: specific literal action that does not include variables as with the schema
        # for example, the action schema 'Load(c, p, a)' can represent the concrete actions 'Load(C1, P1, SFO)'
        # or 'Load(C2, P2, JFK)'.  The actions for the planning problem must be concrete because the problems in
        # forward search and Planning Graphs must use Propositional Logic

        def load_actions():
            """ Create all concrete Load actions and return a list

            :return: list of Action objects
            """
            loads = []
            for c in self.cargos:
                for p in self.planes:
                    for a in self.airports:
                        precond_pos = [expr("At({}, {})".format(p, a)),
                                       expr("At({}, {})".format(c, a))]
                        precond_neg = []
                        effect_add = [expr("In({}, {})".format(c, p))]
                        effect_rem = [expr("At({}, {})".format(c, a))]
                        load = Action(expr("Load({}, {}, {})".format(c, p, a)),
                                      [precond_pos, precond_neg],
                                      [effect_add, effect_rem])
                        loads.append(load)
            return loads

        def unload_actions():
            """ Create all concrete Unload ground actions
            from the domain Unload ground action and return a list

            :return: list of Action objects
            """
            unloads = []
            for c in self.cargos:
                for p in self.planes:
                    for a in self.airports:
                        precond_pos = [expr("At({}, {})".format(p, a)),
                                       expr("In({}, {})".format(c, p))]
                        precond_neg = []
                        effect_add = [expr("At({}, {})".format(c, a))]
                        effect_rem = [expr("In({}, {})".format(c, p))]
                        unload = Action(expr("Unload({}, {}, {})".format(c, p, a)),
                                        [precond_pos, precond_neg],
                                        [effect_add, effect_rem])
                        unloads.append(unload)
            return unloads

        def fly_actions():
            """ Create all concrete Fly actions and return a list

            :return: list of Action objects
            """
            flys = []
            for fr in self.airports:
                for to in self.airports:
                    if fr != to:
                        for p in self.planes:
                            precond_pos = [expr("At({}, {})".format(p, fr))]
                            precond_neg = []
                            effect_add = [expr("At({}, {})".format(p, to))]
                            effect_rem = [expr("At({}, {})".format(p, fr))]
                            fly = Action(expr("Fly({}, {}, {})".format(p, fr, to)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            flys.append(fly)
            return flys

        return load_actions() + unload_actions() + fly_actions()

    def actions(self, state: str) -> list:
        """ Return the actions that can be executed in the given state.

        :param state: str
            state represented as T/F string of mapped fluents (state variables)
            e.g. 'FTTTFF'
        :return: list of Action objects
        """
        possible_actions = []
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        # logging.debug("\nKB Clauses: %r", kb.clauses)

        for action in self.actions_list:
            # logging.debug("\nAction Name / Args: %r / %r", action.name, action.args)
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
        """ Return the state that results from executing the given
        action in the given state. The action must be one of
        self.actions(state).

        :param state: state entering node
        :param action: Action applied
        :return: resulting state after action
        """
        new_state = FluentState([], [])
        old_state = decode_state(state, self.state_map)
        for pos in old_state.pos:
            if pos not in new_state.pos:
                new_state.pos.append(pos)
            if pos in new_state.neg:
                new_state.neg.remove(pos)
        for rem in old_state.neg:
            if rem in new_state.pos:
                new_state.pos.remove(rem)
            if rem not in new_state.neg:
                new_state.neg.append(rem)
        for pos in action.effect_add:
            if pos not in new_state.pos:
                new_state.pos.append(pos)
            if pos in new_state.neg:
                new_state.neg.remove(pos)
        for rem in action.effect_rem:
            if rem in new_state.pos:
                new_state.pos.remove(rem)
            if rem not in new_state.neg:
                new_state.neg.append(rem)
        return encode_state(new_state, self.state_map)

    def goal_test(self, state: str) -> bool:
        """ Test the state to see if goal is reached

        :param state: str representing state
        :return: bool
        """
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
        """ This heuristic uses a planning graph representation of the problem
        state space to estimate the sum of all actions that must be carried
        out from the current state in order to satisfy each individual goal
        condition.
        """
        # requires implemented PlanningGraph class
        pg = PlanningGraph(self, node.state)
        pg_levelsum = pg.h_levelsum()
        return pg_levelsum

    def h_ignore_preconditions(self, node: Node):
        """ This heuristic estimates the minimum number of actions that must be
        carried out from the current state in order to satisfy all of the goal
        conditions by ignoring the preconditions required for an action to be
        executed.
        """
        # Implemented with reference to Russell-Norvig Ed-3 10.2.3
        count = 0
        kb = PropKB()
        kb.tell(decode_state(node.state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                count += 1
        return count

    def h_ignore_delete_lists(self, node: Node):
        """
        This heuristic estimates the minimum number of actions that must be
        carried out from the current state in order to satisfy all of the goal
        conditions. It achieves this by assuming all goals and preconditions
        contain only positive literals and creates a relaxed version of the
        original problem that's easier to solve by removing the delete lists
        from all actions (i.e. removing all negative effects) so no
        action ever undoes progress made by another action.
        """
        # Implemented with reference to Russell-Norvig Ed-3 10.2.3, p. 377
        count = 0
        kb = PropKB()
        kb.tell(decode_state(node.state, self.state_map).pos_sentence())
        for action in self.actions_list:
            for clause in self.goal:
                if clause in action.effect_rem:
                    count += 1
            return count


def air_cargo_p1() -> AirCargoProblem:
    cargos = ['C1', 'C2']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           ]
    neg = [expr('At(C2, SFO)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('At(C1, JFK)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('At(P1, JFK)'),
           expr('At(P2, SFO)'),
           ]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)

def air_cargo_p2() -> AirCargoProblem:
    # Implementation of Problem 2 definition
    cargos = ['C1', 'C2', 'C3']
    planes = ['P1', 'P2', 'P3']
    airports = ['JFK', 'SFO', 'SYD']
    pos = [expr('At(C1, SYD)'),
           expr('At(C2, JFK)'),
           expr('At(C3, SFO)'),
           expr('At(P1, SYD)'),
           expr('At(P2, JFK)'),
           expr('At(P3, SFO)'),
           ]
    neg = [expr('At(C1, JFK)'),
           expr('At(C1, SFO)'),
           expr('At(C2, SFO)'),
           expr('At(C2, SYD)'),
           expr('At(C3, JFK)'),
           expr('At(C3, SYD)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('In(C1, P3)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('In(C2, P3)'),
           expr('In(C3, P1)'),
           expr('In(C3, P2)'),
           expr('In(C3, P3)'),
           expr('At(P1, JFK)'),
           expr('At(P1, SFO)'),
           expr('At(P2, SFO)'),
           expr('At(P2, SYD)'),
           expr('At(P3, JFK)'),
           expr('At(P3, SYD)'),
           ]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C3, SYD)'),
            ]

    return AirCargoProblem(cargos, planes, airports, init, goal)

def air_cargo_p3() -> AirCargoProblem:
    # Implementation of Problem 3 definition
    cargos = ['C1', 'C2', 'C3', 'C4']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO', 'SYD', 'PER']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(C3, SYD)'),
           expr('At(C4, PER)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           ]
    neg = [expr('At(C1, JFK)'),
           expr('At(C1, SYD)'),
           expr('At(C1, PER)'),
           expr('At(C2, SFO)'),
           expr('At(C2, SYD)'),
           expr('At(C2, PER)'),
           expr('At(C3, JFK)'),
           expr('At(C3, SFO)'),
           expr('At(C3, PER)'),
           expr('At(C4, JFK)'),
           expr('At(C4, SFO)'),
           expr('At(C4, SYD)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('In(C3, P1)'),
           expr('In(C3, P2)'),
           expr('In(C4, P1)'),
           expr('In(C4, P2)'),
           expr('At(P1, JFK)'),
           expr('At(P1, SYD)'),
           expr('At(P1, PER)'),
           expr('At(P2, SFO)'),
           expr('At(P2, SYD)'),
           expr('At(P2, PER)'),
           ]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C3, JFK)'),
            expr('At(C4, SFO)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)

# IMPORTANT NOTE: Run "Performance Comparison" directly (see Readme) with:
#   - python3 run_search.py -m OR
#   - python3 run_search.py -p 1 2 3 -s 1 2 -s 1 2 3 4 5 6 7 8 9 10

# if __name__ == '__main__':
#     p = air_cargo_p1()
#     print("**** Air Cargo Problem 1 setup ****")
#     print("Initial state for this problem is {}".format(p.initial))
#     print("Actions for this domain are:")
#     for a in p.actions_list:
#         print('   {}{}'.format(a.name, a.args))
#     print("Fluents in this problem are:")
#     for f in p.state_map:
#         print('   {}'.format(f))
#     print("Goal requirement for this problem are:")
#     for g in p.goal:
#         print('   {}'.format(g))
#     print()
#     print("*** Breadth First Search")
#     run_search(p, breadth_first_search)
#     print("*** Depth First Search")
#     run_search(p, depth_first_graph_search)
#     print("*** Uniform Cost Search")
#     run_search(p, uniform_cost_search)
#     print("*** Greedy Best First Graph Search - null heuristic")
#     run_search(p, greedy_best_first_graph_search, parameter=p.h_1)
#     print("*** A-star null heuristic")
#     run_search(p, astar_search, p.h_1)
#     print("*** A-star ignore preconditions heuristic")
#     run_search(p, astar_search, p.h_ignore_preconditions)
#     print("*** A-star ignore delete lists heuristic")
#     run_search(p, astar_search, p.h_ignore_delete_lists)
#     print("*** A-star levelsum heuristic")
#     run_search(p, astar_search, p.h_pg_levelsum)
#
# # TODO - Repeat for air_cargo_p1()
#
# # TODO - Repeat for air_cargo_p2()