"""Node class represents a node in UD trees."""
import collections.abc

from udapi.block.write.textmodetrees import TextModeTrees
from udapi.core.feats import Feats

# Pylint complains when we access e.g. node.parent._children or root._descendants
# because it does not know that node.parent is the same class (Node)
# and Root is a "friend" class of Node, so accessing underlined attributes is OK and intended.
# Moreover, pylint has false-positive no-member alarms when accessing node.root._descendants
# (pylint thinks node.root returns a Node instance, but actually it returns a Root instance).
# pylint: disable=protected-access,no-member

# 7 instance attributes and 20 public methods are too low limits (CoNLL-U has 10 columns)
# The set of public attributes/properties and methods of Node was well-thought.
# pylint: disable=too-many-instance-attributes,too-many-public-methods

class Node(object):
    """Class for representing nodes in Universal Dependency trees."""

    # TODO: Benchmark memory and speed of slots vs. classic dict.
    # With Python 3.5 split dict, slots may not be better.
    # TODO: Should not we include __weakref__ in slots?
    __slots__ = [
        # Word index, integer starting at 1 for each new sentence.
        'ord',       # Word-order index of the node (root has 0).
        'form',      # Word form or punctuation symbol.
        'lemma',     # Lemma of word form.
        'upos',      # Universal PoS tag
        'xpos',      # Language-specific part-of-speech tag; underscore if not available.
        'deprel',    # UD dependency relation to the HEAD (root iff HEAD = 0).
        'misc',      # Any other annotation.
        '_raw_deps', # Enhanced dependencies (head-deprel pairs) in their original CoNLLU format.
        '_deps',     # Deserialized enhanced dependencies in a list of {parent, deprel} dicts.
        '_feats',    # Morphological features as udapi.core.feats.Feats object.
        '_parent',   # Parent node.
        '_children', # Ord-ordered list of child nodes.
        '_mwt',      # multi-word token in which this word participates
    ]

    def __init__(self, data=None):
        """Create new node and initialize its attributes with data."""
        # Initialization of the (A) list.
        self.ord = None
        self.form = None
        self.lemma = None
        self.upos = None
        self.xpos = None
        self.deprel = None
        self.misc = None

        # Initialization of the (B) list.
        self._raw_deps = '_'
        self._deps = None
        self._feats = Feats()
        self._parent = None
        self._children = list()
        self._mwt = None

        # If given, set the node using data from arguments.
        if data is not None:
            for name in data:
                setattr(self, name, data[name])

    def __str__(self):
        """Pretty print of the Node object."""
        parent_ord = None
        if self.parent is not None:
            parent_ord = self.parent.ord
        return "<%d, %s, %s, %s>" % (self.ord, self.form, parent_ord, self.deprel)

    @property
    def raw_feats(self):
        """String serialization of morphological features as stored in CoNLL-U files."""
        return str(self._feats)

    @property
    def feats(self):
        """Return morphological features as a `Feats` object (dict)."""
        return self._feats

    @feats.setter
    def feats(self, value):
        """Set morphological features (the value can be string or dict)."""
        if isinstance(value, str):
            self._feats.set_string(value)
        elif isinstance(value, collections.abc.Mapping):
            self._feats = Feats(value)

    @property
    def raw_deps(self):
        """String serialization of enhanced dependencies as stored in CoNLL-U files.

        After the access to the raw enhanced dependencies,
        provide the serialization if they were deserialized already.
        """
        if self._deps is not None:
            serialized_deps = []
            for secondary_dependence in self._deps:
                serialized_deps.append('%d:%s' % (secondary_dependence[
                    'parent'].ord, secondary_dependence['deprel']))
            self._raw_deps = '|'.join(serialized_deps)
        return self._raw_deps

    @raw_deps.setter
    def raw_deps(self, value):
        """Set serialized enhanced dependencies (the new value is a string).

        When updating raw secondary dependencies,
        delete the current version of the deserialized data.
        """
        self._raw_deps = str(value)
        self._deps = None

    @property
    def deps(self):
        """Return enhanced dependencies as a Python list of dicts.

        After the first access to the enhanced dependencies,
        provide the deserialization of the raw data and save deps to the list.
        """
        if self._deps is None:
            # Obtain a list of all nodes in the dependency tree.
            nodes = [self.root] + self.root.descendants()

            # Create a list of secondary dependencies.
            self._deps = list()

            if self._raw_deps == '_':
                return self._deps

            for raw_dependency in self._raw_deps.split('|'):
                head, deprel = raw_dependency.split(':')
                parent = nodes[int(head)]
                self._deps.append({'parent': parent, 'deprel': deprel})

        return self._deps

    @deps.setter
    def deps(self, value):
        """Set deserialized enhanced dependencies (the new value is a list of dicts)."""
        self._deps = value

    @property
    def parent(self):
        """Return dependency parent (head) node."""
        return self._parent

    @parent.setter
    def parent(self, new_parent):
        """Set a new dependency parent node.

        Check if the parent assignment is valid (no cycles) and assign
        a new parent (dependency head) for the current node.
        If the node had a parent, it is detached first
        (from the list of original parent's children).
        """
        # If the parent is already assigned, return.
        if self.parent == new_parent:
            return

        # The node itself couldn't be assigned as a parent.
        if self == new_parent:
            raise ValueError('Could not set the node itself as a parent: %s' % self)

        # Check if the current Node is not an antecedent of the new parent.
        climbing_node = new_parent
        while not climbing_node.is_root:
            if climbing_node == self:
                raise Exception('Setting the parent would lead to a loop: %s' % self)
            climbing_node = climbing_node.parent

        # Remove the current Node from the children of the old parent.
        if self.parent:
            self.parent._children = [node for node in self.parent.children if node != self]

        # Set the new parent.
        self._parent = new_parent

        # Append the current node the the new parent children.
        new_parent._children = sorted(new_parent.children + [self], key=lambda child: child.ord)

    @property
    def children(self):
        """Return a list of dependency children (direct dependants) nodes.

        The returned nodes are sorted by their ord.
        Note that node.children is a property, not a method,
        so if you want all the children of a node (excluding the node itself),
        you should not use node.children(), but just
         node.children
        However, the returned result is a callable list, so you can use
         nodes1 = node.children(add_self=True)
         nodes2 = node.children(following_only=True)
         nodes3 = node.children(preceding_only=True)
         nodes4 = node.children(preceding_only=True, add_self=True)
        as a shortcut for
         nodes1 = sorted([node] + node.children, key=lambda n: n.ord)
         nodes2 = [n for n in node.children if n.ord > node.ord]
         nodes3 = [n for n in node.children if n.ord < node.ord]
         nodes4 = [n for n in node.children if n.ord < node.ord] + [node]
        See documentation of ListOfNodes for details.
        """
        return ListOfNodes(self._children, origin=self)

    @property
    def root(self):
        """Return the (technical) root node of the whole tree."""
        node = self
        while node.parent:
            node = node.parent
        return node

    @property
    def descendants(self):
        """Return a list of all descendants of the current node.

        The returned nodes are sorted by their ord.
        Note that node.descendants is a property, not a method,
        so if you want all the descendants of a node (excluding the node itself),
        you should not use node.descendants(), but just
         node.descendants
        However, the returned result is a callable list, so you can use
         nodes1 = node.descendants(add_self=True)
         nodes2 = node.descendants(following_only=True)
         nodes3 = node.descendants(preceding_only=True)
         nodes4 = node.descendants(preceding_only=True, add_self=True)
        as a shortcut for
         nodes1 = sorted([node] + node.descendants, key=lambda n: n.ord)
         nodes2 = [n for n in node.descendants if n.ord > node.ord]
         nodes3 = [n for n in node.descendants if n.ord < node.ord]
         nodes4 = [n for n in node.descendants if n.ord < node.ord] + [node]
        See documentation of ListOfNodes for details.
        """
        return ListOfNodes(sorted(self.unordered_descendants(), key=lambda n: n.ord), origin=self)

    def is_descendant_of(self, node):
        """Is the current node a descendant of the node given as argument?"""
        climber = self.parent
        while climber:
            if climber == node:
                return True
            climber = climber.parent
        return False

    def create_child(self):
        """Create and return a new child of the current node."""
        new_node = Node()
        new_node.ord = len(self.root._descendants) + 1
        self.root._descendants.append(new_node)
        self.children.append(new_node)
        new_node.parent = self
        return new_node

    # TODO: make private: _unordered_descendants
    def unordered_descendants(self):
        """Return a list of all descendants in any order."""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.unordered_descendants())
        return descendants

    @staticmethod
    def is_root():
        """Is the current node a (technical) root?

        Returns False for all Node instances, irrespectively of whether is has a parent or not.
        True is returned only by instances of udapi.core.root.Root.
        """
        return False

    def remove(self):
        """Delete this node and all its descendants."""
        self.parent.children = [child for child in self.parent.children if child != self]
        self.root._update_ordering()

    # TODO: make private: _shift
    def shift(self, reference_node, after=0, move_subtree=0, reference_subtree=0):
        """Internal method for changing word order."""
        nodes_to_move = [self]

        if move_subtree:
            nodes_to_move.extend(self.descendants())

        reference_ord = reference_node.ord

        if reference_subtree:
            for node in [n for n in reference_node.descendants() if n != self]:
                if (after and node.ord > reference_ord) or (not after and node.ord < reference_ord):
                    reference_ord = node.ord

        common_delta = 0.5 if after else -0.5

        # TODO: can we use some sort of epsilon instead of choosing a silly
        # upper bound for out-degree?
        for node_to_move in nodes_to_move:
            node_to_move.ord = reference_ord + common_delta + \
                (node_to_move.ord - self.ord) / 100000.

        self.root._update_ordering()

    # TODO add without_children kwarg
    def shift_after_node(self, reference_node):
        """Shift this node after the reference_node."""
        self.shift(reference_node, after=1, move_subtree=1, reference_subtree=0)

    def shift_before_node(self, reference_node):
        """Shift this node after the reference_node."""
        self.shift(reference_node, after=0, move_subtree=1, reference_subtree=0)

    def shift_after_subtree(self, reference_node, without_children=0):
        """Shift this node (and its subtree) after the subtree rooted by reference_node.

        Args:
        without_children: shift just this node without its subtree?
        """
        self.shift(reference_node, after=1, move_subtree=not without_children, reference_subtree=1)

    def shift_before_subtree(self, reference_node, without_children=0):
        """Shift this node (and its subtree) before the subtree rooted by reference_node.

        Args:
        without_children: shift just this node without its subtree?
        """
        self.shift(reference_node, after=0, move_subtree=not without_children, reference_subtree=1)

    @property
    def prev_node(self):
        """Return the previous node according to word order."""
        new_ord = self.ord - 1
        if new_ord < 0:
            return None
        if new_ord == 0:
            return self.root
        return self.root._descendants[self.ord - 1]

    @property
    def next_node(self):
        """Return the following node according to word order."""
        # Note that all_nodes[n].ord == n+1
        try:
            return self.root._descendants[self.ord]
        except IndexError:
            return None

    def is_leaf(self):
        """Is this node a leaf, ie. a node without any children?"""
        return not self.children

    def get_attrs(self, attrs, undefs=None):
        """Return multiple attributes, possibly subsitituting empty ones.

        Args:
        attrs: A list of attribute names, e.g. ['form', 'lemma'].
        undefs: A value to be used instead of None for empty (undefined) values.
        """
        values = [getattr(self, name) for name in attrs]
        if undefs is not None:
            values = [x if x is not None else undefs for x in values]
        return values

    def compute_sentence(self):
        """Return a string representing this subtree's text (detokenized).

        Compute the string by concatenating forms of nodes
        (words and multi-word tokens) and joining them with a single space,
        unless the node has SpaceAfter=No in its misc.
        If called on root this method returns a string suitable for storing
        in root.text (but it is not stored there automatically).

        Technical detail:
        If called on root, the root's form (<ROOT>) is not included in the string.
        If called on non-root nodeA, nodeA's form is included in the string,
        i.e. internally descendants(add_self=True) is used.
        """
        string = ''
        # TODO: use multi-word tokens instead of words where possible.
        # TODO: self.descendants(add_self=not self.is_root()):
        for node in self.descendants():
            string += node.form
            if node.misc.find('SpaceAfter=No') == -1:
                string += ' '
        return string

    def print_subtree(self, **kwargs):
        """Print ASCII visualization of the dependency structure of this subtree.

        This method is useful for debugging.
        Internally udapi.block.write.textmodetrees.TextModeTrees is used for the printing.
        All keyword arguments of this method are passed to its constructor,
        so you can use e.g.:
        files: to redirect sys.stdout to a file
        indent: to have wider trees
        attributes: to override the default list 'form,upos,deprel'
        See TextModeTrees for details and other parameters.
        """
        TextModeTrees(**kwargs).process_tree(self)

    def address(self):
        """Return full (document-wide) id of the node.

        For non-root nodes, the general address format is:
        node.bundle.bundle_id + '/' + node.root.zone + '#' + node.ord,
        e.g. s123/en_udpipe#4. If zone is empty, the slash is excluded as well,
        e.g. s123#4.
        """
        return '%s#%d' % (self.root.address(), self.ord)

    @property
    def multiword_token(self):
        """Return the multi-word token which includes this node, or None.

        If this node represents a (syntactic) word which is part of a multi-word token,
        this method returns the instance of udapi.core.mwt.MWT.
        If this nodes is not part of any multi-word token, this method returns None.
        """
        return self._mwt


class ListOfNodes(list):
    """Helper class for results of node.children and node.descendants.

    Python distinguishes properties, e.g. node.form ... no brackets,
    and methods, e.g. node.remove() ... brackets necessary.
    It is useful (and expected by Udapi users) to use properties,
    so one can do e.g. node.form += "suffix".
    It is questionable whether node.parent, node.root, node.children etc.
    should be properties or methods. The problem of methods is that
    if users forget the brackets, the error may remain unnoticed
    because the result is interpreted as a method reference.
    The problem of properties is that they cannot have any parameters.
    However, we would like to allow e.g. node.children(add_self=True).

    This class solves the problem: node.children and node.descendants
    are properties which return instances of this clas ListOfNodes.
    This class implements the method __call__, so one can use e.g.
    nodes = node.children
    nodes = node.children()
    nodes = node.children(add_self=True, following_only=True)
    """
    def __init__(self, iterable, origin):
        """Create a new ListOfNodes.

        Args:
        iterable: a list of nodes
        origin: a node which is the parent/ancestor of these nodes
        """
        super().__init__(iterable)
        self.origin = origin

    def __call__(self, add_self=False, following_only=False, preceding_only=False):
        """Returns a subset of nodes contained in this list as specified by the args."""
        if not add_self and not following_only and not preceding_only:
            return self
        result = list(self)
        if add_self:
            result.append(self.origin)
        if preceding_only:
            result = [x for x in result if x.ord <= self.origin.ord]
        if following_only:
            result = [x for x in result if x.ord >= self.origin.ord]
        return sorted(result, key=lambda node: node.ord)
