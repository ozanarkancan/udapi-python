"""Block MarkBugs for checking suspicious/wrong constructions in UD v2.

See http://universaldependencies.org/release_checklist.html#syntax
and http://universaldependencies.org/svalidation.html
IMPORTANT: the svalidation.html overview is not generated by this code,
but by SETS-search-interface rules, which may give different results than this code.

Usage:
udapy -s ud.MarkBugs < in.conllu > marked.conllu 2> log.txt

Errors are both logged to stderr and marked within the nodes' MISC field,
e.g. `node.misc['Bug'] = 'aux-chain'`, so the output conllu file can be
searched for "Bug=" occurences.

Author: Martin Popel
based on descriptions at http://universaldependencies.org/svalidation.html
"""
import logging
import collections

from udapi.core.block import Block

REQUIRED_FEATURE_FOR_UPOS = {
    'PRON': 'PronType',
    'DET': 'PronType',
    'NUM': 'NumType',
    'VERB': 'VerbForm',
}

class MarkBugs(Block):
    """Block for checking suspicious/wrong constructions in UD v2."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stats = collections.Counter()

    def log(self, node, short_msg, long_msg):
        """Log node.address() + long_msg and add ToDo=short_msg to node.misc."""
        # TODO: these should be logging.debug and udapy should have --debug flag
        logging.warning('node %s %s: %s', node.address(), short_msg, long_msg)
        if node.misc['Bug']:
            node.misc['Bug'] += ',' + short_msg
        else:
            node.misc['Bug'] = short_msg
        self.stats[short_msg] += 1

    # pylint: disable=too-many-branches
    def process_node(self, node):
        deprel, upos, feats = node.deprel, node.upos, node.feats
        parent = node.parent

        for dep in ('aux', 'fixed', 'appos'):
            if deprel == dep and parent.deprel == dep:
                self.log(node, dep + '-chain', dep + ' dependencies should not form a chain.')

        for dep in ('flat', 'fixed', 'conj', 'appos'):
            if deprel == dep and node.precedes(parent):
                self.log(node, dep + '-rightheaded',
                         dep + ' relations should be left-headed, not right.')

        if deprel == 'cop' and upos not in ('AUX', 'PRON'):
            self.log(node, 'cop-upos', 'deprel=cop upos!=AUX|PRON (but %s)' % upos)

        if deprel == 'mark' and upos == 'PRON':
            self.log(node, 'mark-upos', 'deprel=mark upos=PRON')

        if deprel == 'det' and upos not in ('DET', 'PRON'):
            self.log(node, 'det-upos', 'deprel=det upos!=DET|PRON (but %s)' % upos)

        if deprel == 'punct' and upos != 'PUNCT':
            self.log(node, 'punct-upos', 'deprel=punct upos!=PUNCT (but %s)' % upos)

        for i_upos, i_feat in REQUIRED_FEATURE_FOR_UPOS.items():
            if upos == i_upos and not node.feats[i_feat]:
                self.log(node, 'no-' + i_feat, 'upos=%s but %s feature is missing' % (upos, i_feat))

        if feats['VerbForm'] == 'Fin':
            if upos not in ('VERB', 'AUX'):
                self.log(node, 'finverb-upos', 'VerbForm=Fin upos!=VERB|AUX (but %s)' % upos)
            if not feats['Mood']:
                self.log(node, 'finverb-mood', 'VerbForm=Fin but Mood feature is missing')

        if feats['Degree'] and upos not in ('ADJ', 'ADV'):
            self.log(node, 'degree-upos',
                     'Degree=%s upos!=ADJ|ADV (but %s)' % (feats['Degree'], upos))

        subject_children = [n for n in node.children if 'subj' in n.deprel]
        if len(subject_children) > 1:
            self.log(node, 'multi-subj', 'More than one [nc]subj(:pass)? child')

        object_children = [n for n in node.children if n.deprel in ('obj', 'ccomp')]
        if len(object_children) > 1:
            self.log(node, 'multi-obj', 'More than one obj|ccomp child')

        if parent.upos == 'ADP' and deprel not in ('conj', 'cc', 'punct', 'fixed'):
            self.log(node, 'adp-child', 'parent.upos=ADP deprel!=conj|cc|punct|fixed')

        # In addition to http://universaldependencies.org/svalidation.html
        if parent.deprel == 'punct':
            self.log(node, 'punct-child', 'parent.deprel=punct')

    def process_end(self):
        logging.warning('ud.MarkBugs Error Overview:')
        total = 0
        for bug, count in sorted(self.stats.items(), key=lambda pair: pair[1]):
            total += count
            logging.warning('%20s %10d', bug, count)
        logging.warning('%20s %10d', 'TOTAL', total)
