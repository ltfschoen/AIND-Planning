from aimacode.planning import Action
from aimacode.search import Problem
from aimacode.utils import expr
from lp_utils import decode_state

import my_logging
from my_logging import *
my_logging.setup_log_level()

class PgNode():
    ''' Base class for planning graph nodes.

    includes instance sets common to both types of nodes used in a planning graph
    parents: the set of nodes in the previous level
    children: the set of nodes in the subsequent level
    mutex: the set of sibling nodes that are mutually exclusive with this node
    '''

    def __init__(self):
        self.parents = set()
        self.children = set()
        self.mutex = set()

    def is_mutex(self, other) -> bool:
        ''' Boolean test for mutual exclusion

        :param other: PgNode
            the other node to compare with
        :return: bool
            True if this node and the other are marked mutually exclusive (mutex)
        '''
        if other in self.mutex:
            return True
        return False

    def show(self):
        ''' helper print for debugging shows counts of parents, children, siblings

        :return:
            print only
        '''
        print("{} parents".format(len(self.parents)))
        print("{} children".format(len(self.children)))
        print("{} mutex".format(len(self.mutex)))


class PgNode_s(PgNode):
    '''
    A planning graph node representing a state (literal fluent) from a planning
    problem.

    Args:
    ----------
    symbol : str
        A string representing a literal expression from a planning problem
        domain.

    is_pos : bool
        Boolean flag indicating whether the literal expression is positive or
        negative.
    '''

    def __init__(self, symbol: str, is_pos: bool):
        ''' S-level Planning Graph node constructor

        :param symbol: expr
        :param is_pos: bool
        Instance variables calculated:
            literal: expr
                    fluent in its literal form including negative operator if applicable
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous A level; initially empty
            children: set of nodes connected to this node in next A level; initially empty
            mutex: set of sibling S-nodes that this node has mutual exclusion with; initially empty
        '''
        PgNode.__init__(self)
        self.symbol = symbol
        self.is_pos = is_pos
        self.literal = expr(self.symbol)
        if not self.is_pos:
            self.literal = expr('~{}'.format(self.symbol))

    def show(self):
        '''helper print for debugging shows literal plus counts of parents, children, siblings

        :return:
            print only
        '''
        print("\n*** {}".format(self.literal))
        PgNode.show(self)

    def __eq__(self, other):
        '''equality test for nodes - compares only the literal for equality

        :param other: PgNode_s
        :return: bool
        '''
        if isinstance(other, self.__class__):
            return (self.symbol == other.symbol) \
                   and (self.is_pos == other.is_pos)

    def __not_eq__(self, other):
        '''inequality test for nodes - compares only the literal for equality

        :param other: PgNode_s
        :return: bool
        '''
        if isinstance(other, self.__class__):
            return (self.symbol == other.symbol) \
                   and (self.is_pos != other.is_pos)

    def __hash__(self):
        return hash(self.symbol) ^ hash(self.is_pos)


class PgNode_a(PgNode):
    '''A-type (action) Planning Graph node - inherited from PgNode
    '''

    def __init__(self, action: Action):
        '''A-level Planning Graph node constructor

        :param action: Action
            a ground action, i.e. this action cannot contain any variables
        Instance variables calculated:
            An A-level will always have an S-level as its parent and an S-level as its child.
            The preconditions and effects will become the parents and children of the A-level node
            However, when this node is created, it is not yet connected to the graph
            prenodes: set of *possible* parent S-nodes
            effnodes: set of *possible* child S-nodes
            is_persistent: bool   True if this is a persistence action, i.e. a no-op action
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous S level; initially empty
            children: set of nodes connected to this node in next S level; initially empty
            mutex: set of sibling A-nodes that this node has mutual exclusion with; initially empty
       '''
        PgNode.__init__(self)
        self.action = action
        self.prenodes = self.precond_s_nodes()
        self.effnodes = self.effect_s_nodes()
        self.is_persistent = False
        if self.prenodes == self.effnodes:
            self.is_persistent = True

    def show(self):
        '''helper print for debugging shows action plus counts of parents, children, siblings

        :return:
            print only
        '''
        print("\n*** {}{}".format(self.action.name, self.action.args))
        PgNode.show(self)

    def precond_s_nodes(self):
        '''precondition literals as S-nodes (represents possible parents for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `prenodes` attribute.

        :return: set of PgNode_s
        '''
        nodes = set()
        for p in self.action.precond_pos:
            n = PgNode_s(p, True)
            nodes.add(n)
        for p in self.action.precond_neg:
            n = PgNode_s(p, False)
            nodes.add(n)
        return nodes

    def effect_s_nodes(self):
        '''effect literals as S-nodes (represents possible children for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `effnodes` attribute.

        :return: set of PgNode_s
        '''
        nodes = set()
        for e in self.action.effect_add:
            n = PgNode_s(e, True)
            nodes.add(n)
        for e in self.action.effect_rem:
            n = PgNode_s(e, False)
            nodes.add(n)
        return nodes

    def __eq__(self, other):
        '''equality test for nodes - compares only the action name for equality

        :param other: PgNode_a
        :return: bool
        '''
        if isinstance(other, self.__class__):
            return (self.action.name == other.action.name) \
                   and (self.action.args == other.action.args)

    def __hash__(self):
        return hash(self.action.name) ^ hash(self.action.args)


def mutexify(node1: PgNode, node2: PgNode):
    ''' adds sibling nodes to each other's mutual exclusion (mutex) set. These should be sibling nodes!

    :param node1: PgNode (or inherited PgNode_a, PgNode_s types)
    :param node2: PgNode (or inherited PgNode_a, PgNode_s types)
    :return:
        node mutex sets modified
    '''
    if type(node1) != type(node2):
        raise TypeError('Attempted to mutex two nodes of different types')
    node1.mutex.add(node2)
    node2.mutex.add(node1)

def is_effect_mutex(eff1, eff2):
    return True if [e1 for e1 in eff1 if e1 in eff2] else False

class PlanningGraph():
    '''
    A planning graph as described in chapter 10 of the AIMA text. The planning
    graph can be used to reason about 
    '''

    def __init__(self, problem: Problem, state: str, serial_planning=True):
        '''
        :param problem: PlanningProblem (or subclass such as AirCargoProblem or HaveCakeProblem)
        :param state: str (will be in form TFTTFF... representing fluent states)
        :param serial_planning: bool (whether or not to assume that only one action can occur at a time)
        Instance variable calculated:
            fs: FluentState
                the state represented as positive and negative fluent literal lists
            all_actions: list of the PlanningProblem valid ground actions combined with calculated no-op actions
            s_levels: list of sets of PgNode_s, where each set in the list represents an S-level in the planning graph
            a_levels: list of sets of PgNode_a, where each set in the list represents an A-level in the planning graph
        '''
        self.problem = problem
        self.fs = decode_state(state, problem.state_map)
        self.serial = serial_planning
        self.all_actions = self.problem.actions_list + self.noop_actions(self.problem.state_map)
        self.s_levels = []
        self.a_levels = []
        self.create_graph()

    def noop_actions(self, literal_list):
        '''create persistent action for each possible fluent

        "No-Op" actions are virtual actions (i.e., actions that only exist in
        the planning graph, not in the planning problem domain) that operate
        on each fluent (literal expression) from the problem domain. No op
        actions "pass through" the literal expressions from one level of the
        planning graph to the next.

        The no-op action list requires both a positive and a negative action
        for each literal expression. Positive no-op actions require the literal
        as a positive precondition and add the literal expression as an effect
        in the output, and negative no-op actions require the literal as a
        negative precondition and remove the literal expression as an effect in
        the output.

        This function should only be called by the class constructor.

        :param literal_list:
        :return: list of Action
        '''
        action_list = []
        for fluent in literal_list:
            act1 = Action(expr("Noop_pos({})".format(fluent)), ([fluent], []), ([fluent], []))
            action_list.append(act1)
            act2 = Action(expr("Noop_neg({})".format(fluent)), ([], [fluent]), ([], [fluent]))
            action_list.append(act2)
        return action_list

    def create_graph(self):
        ''' build a Planning Graph as described in Russell-Norvig 3rd Ed 10.3 or 2nd Ed 11.4

        The S0 initial level has been implemented for you.  It has no parents and includes all of
        the literal fluents that are part of the initial state passed to the constructor.  At the start
        of a problem planning search, this will be the same as the initial state of the problem.  However,
        the planning graph can be built from any state in the Planning Problem

        This function should only be called by the class constructor.

        :return:
            builds the graph by filling s_levels[] and a_levels[] lists with node sets for each level
        '''
        # the graph should only be built during class construction
        if (len(self.s_levels) != 0) or (len(self.a_levels) != 0):
            raise Exception(
                'Planning Graph already created; construct a new planning graph for each new state in the planning sequence')

        # initialize S0 to literals in initial state provided.
        leveled = False
        level = 0
        self.s_levels.append(set())  # S0 set of s_nodes - empty to start
        # for each fluent in the initial state, add the correct literal PgNode_s
        for literal in self.fs.pos:
            self.s_levels[level].add(PgNode_s(literal, True))
        for literal in self.fs.neg:
            self.s_levels[level].add(PgNode_s(literal, False))
        # no mutexes at the first level

        # continue to build the graph alternating A, S levels until last two S levels contain the same literals,
        # i.e. until it is "leveled" (Section 10.3 AIMA text, pg 381)
        while not leveled:
            self.add_action_level(level)
            self.update_a_mutex(self.a_levels[level])

            level += 1
            self.add_literal_level(level)
            self.update_s_mutex(self.s_levels[level])

            if self.s_levels[level] == self.s_levels[level - 1]:
                leveled = True

    def add_action_level(self, level):
        ''' Add A-Level (action) to the Planning Graph per Section 10.3 AIMA text, pg 381

        - Append a Set to Literal Action-Level (A-Level) (to store Action Nodes (no duplicates)
        - Declare Literal State-Level (S-Level) Nodes in current level
        - Iterate all_actions (list of all possible PlanningProblem valid ground actions combined with calculated no-op actions)
            - Declare Current Action using PgNode_a A-type (action) Planning Graph node object constructor
            - Check iff all prerequisite literals for the proposed PgNode_a hold for the Current S-Level including:
            Check to see if proposed PgNode_a has prenodes (set of possible Parent Precondition S-Nodes)
            that are a subset of the Current S-Level (possible Parent).

                - If Current S-Level Nodes is subset of PgNode_a's prenodes
                - Iterate all Current S-Level Nodes
                    - If Current S-Level Node is in PgNode_a's prenodes:
                    Add Current Action Node object (PgNode_a) to "children" of Current S-Level Node.
                    Add Current S-Level Node to "parents" of Current Action Node object (PgNode_a).

                - Add the Current Action Node object (PgNode_a) to the Current A-Level Nodes in Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds A nodes to the current level in self.a_levels[level]
        '''
        self.a_levels.append(set())
        current_s_nodes = self.s_levels[level]
        count_a_levels_before = len(self.a_levels[level])
        count_subsets = 0; count_total = 0
        for a in self.all_actions:
            a_node = PgNode_a(a)
            if a_node.prenodes.issubset(current_s_nodes):
                for s_node in current_s_nodes:
                    if s_node in a_node.prenodes:
                        s_node.children.add(a_node)
                        a_node.parents.add(s_node)
                self.a_levels[level].add(a_node)
                count_subsets += 1
            count_total += 1
        count_a_levels_after = len(self.a_levels[level])
        logging.debug("\nAdded %r action nodes (found to be subsets) out of %r to current A-level nodes changing count from %r to %r.", count_subsets, count_total, count_a_levels_before, count_a_levels_after)

    def add_literal_level(self, level):
        ''' Add an S-Level (literal) to the Planning Graph per Section 10.3 AIMA text, pg 381

        - Append a Set to Literal State-Level (S-Level) (to store Literal Effect Nodes (no duplicates)
        - Declare Parent Literal Action-Level (A-Level) Nodes in previous level
        - Iterate Parent Literal A-Level Nodes
            - Declare Effnodes of Parent Literal A-Level Node
            - Iterate list of S-Level Nodes (Effnodes) representing Effects of Parent Action
                - If find an Effnode of current Parent Action Node that equals current Existing S-Level Node then:
                Add current Existing S-Level Node's "parents" property with the current Parent Action Node.
                Add current Parent Action Node's "children" property with the current Existing S-Level Node.
            - If Effnode of current Parent Action Node does not equal Existing S-Level Node then:
            Add current Parent Action Node to "parents" property of current Effnode.
            Add current Effnode to "children" of current Parent Action Node.
            Add current Effnode to the current Existing S-Level of the Planning Graph as PgNode_s object.

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc
            the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds S nodes to the current level in self.s_levels[level]
        '''
        self.s_levels.append(set())
        parent_a_nodes = self.a_levels[level-1]
        count_s_levels_before = len(self.s_levels[level])
        count_unique = 0; count_total = 0
        for parent_a_node in parent_a_nodes:
            effnodes = parent_a_node.effnodes
            for effnode in effnodes:
                is_unique_node = True
                for existing_s_node in self.s_levels[level]:
                    if effnode == existing_s_node:
                        parent_a_node.children.add(existing_s_node)
                        existing_s_node.parents.add(parent_a_node)
                        is_unique_node = False
                if is_unique_node:
                    parent_a_node.children.add(effnode)
                    effnode.parents.add(parent_a_node)
                    self.s_levels[level].add(effnode)
                    count_unique += 1
                count_total += 1
        count_s_levels_after = len(self.s_levels[level])
        logging.debug("\nAdd %r unique effnodes out of %r to current S-level nodes changing count from %r to %r.", count_unique, count_total, count_s_levels_before, count_s_levels_after)

    def update_a_mutex(self, nodeset):
        ''' Determine and update sibling mutual exclusion for A-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between two actions a given level
        if the planning graph is a serial planning graph and the pair are nonpersistence actions
        or if any of the three conditions hold between the pair:
           Inconsistent Effects
           Interference
           Competing needs

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        '''
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if (self.serialize_actions(n1, n2) or
                        self.inconsistent_effects_mutex(n1, n2) or
                        self.interference_mutex(n1, n2) or
                        self.competing_needs_mutex(n1, n2)):
                    mutexify(n1, n2)

    def serialize_actions(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for mutual exclusion, returning True if the
        planning graph is serial, and if either action is persistent; otherwise
        return False.  Two serial actions are mutually exclusive if they are
        both non-persistent.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''
        #
        if not self.serial:
            return False
        if node_a1.is_persistent or node_a2.is_persistent:
            return False
        return True

    def inconsistent_effects_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for inconsistent effects, returning True if
        one action negates an effect of the other, and False otherwise.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''
        return is_effect_mutex(node_a1.action.effect_add, node_a2.action.effect_rem) or \
               is_effect_mutex(node_a1.action.effect_rem, node_a2.action.effect_add)

    def interference_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for mutual exclusion, returning True if the 
        effect of one action is the negation of a precondition of the other.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''
        return is_effect_mutex(node_a1.action.effect_add, node_a2.action.precond_neg) or \
               is_effect_mutex(node_a1.action.effect_rem, node_a2.action.precond_pos) or \
               is_effect_mutex(node_a2.action.effect_add, node_a1.action.precond_neg) or \
               is_effect_mutex(node_a2.action.effect_rem, node_a1.action.precond_pos)

    def competing_needs_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for mutual exclusion, returning True if one of
        the precondition of one action is mutex with a precondition of the
        other action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''
        actions_s1 = node_a1.parents
        actions_s2 = node_a2.parents
        return True if [(a_s1, a_s2)
                         for a_s1 in actions_s1
                         for a_s2 in actions_s2
                         if a_s1.is_mutex(a_s2)] \
                    else False

    def update_s_mutex(self, nodeset: set):
        ''' Determine and update sibling mutual exclusion for S-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between literals at a given level
        if either of the two conditions hold between the pair:
           Negation
           Inconsistent support

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        '''
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if self.negation_mutex(n1, n2) or self.inconsistent_support_mutex(n1, n2):
                    mutexify(n1, n2)

    def negation_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s) -> bool:
        '''
        Test a pair of state literals for mutual exclusion, returning True if
        one node is the negation of the other, and False otherwise.

        HINT: Look at the PgNode_s.__eq__ defines the notion of equivalence for
        literal expression nodes, and the class tracks whether the literal is
        positive or negative.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        '''
        return node_s1.__not_eq__(node_s2)

    def inconsistent_support_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s):
        '''
        Test a pair of state literals for mutual exclusion, returning True if
        there are no actions that could achieve the two literals at the same
        time, and False otherwise.  In other words, the two literal nodes are
        mutex if all of the actions that could achieve the first literal node
        are pairwise mutually exclusive with all of the actions that could
        achieve the second literal node.

        HINT: The PgNode.is_mutex method can be used to test whether two nodes
        are mutually exclusive.

        - Declare Parents Actions associated with given S-Level Nodes
        - Nested Loop over both Parent Actions
        - Return True if both Parent Actions are mutex or False otherwise

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        '''
        actions_s1 = node_s1.parents
        actions_s2 = node_s2.parents

        return False if [(a_s1, a_s2)
                         for a_s1 in actions_s1
                         for a_s2 in actions_s2
                         if not a_s1.is_mutex(a_s2)] \
                     else True

    def h_levelsum(self) -> int:
        '''Level-Sum Heuristic calculates sum of the level costs of the individual goals
        (admissible if goals independent) per Section 10.3 AIMA text, pg 382

        - Iterate each Goal in Problem
            - Iterate over Levels and associated States in S-Levels object
                - If Goal return Level Sum
                - Else:
                    - Iterate over each State in associated States
                        - If State Literal equals Goal increment Level Sum by level number
                        and return Level Sum
            - If Goal not found in S-Levels object then return Infinite Level Sum

        :return: int
        '''
        level_sum = 0
        for goal in self.problem.goal:
            is_goal = False
            for (level, states) in enumerate(self.s_levels):
                if is_goal:
                    break
                else:
                    for s in states:
                        if goal == s.literal:
                            level_sum += level
                            is_goal = True
                            break
            if not is_goal:
                return float('Inf')
        return level_sum
