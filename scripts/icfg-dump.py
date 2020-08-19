import json
import argparse
import logging
from typing import Tuple
logging.basicConfig(level=logging.WARNING)

p = argparse.ArgumentParser()
p.add_argument('icfg')
p.add_argument('output')
p.add_argument('--params')
args = p.parse_args()

if args.params is None:
    params = {
        "assert": True,
        "label_length": -1
    }
else:
    with open(args.params) as f:
        params = json.load(f)

# First, let's set up some classes to help us.
class Instruction:
    def __init__(self, content: str):
        self.content = content

    def __hash__(self):
        return hash(self.content)
    
    def __eq__(self, other):
        return isinstance(other, Instruction) and\
            self.content == other.content

class BasicBlock:
    def __init__(self, name):
        self.name = name
        self.instructions = list()

    def add_instruction(self, instruction: Instruction):
        self.instructions.append(instruction)

    def __hash__(self):
        return hash((name, tuple(instructions)))

    def __eq__(self, other):
        return isinstance(other, BasicBlock) and\
            self.name == other.name and\
            self.instructions == other.instructions

class Function:
    def __init__(self, name):
        self.name = name
        self.basicblocks = list()

    def add_basicblock(self, basicblock: BasicBlock):
        self.basicblocks.append(basicblock)

    def __hash__(self):
        return hash((name, tuple(basicblocks)))

    def __eq__(self, other):
        return isinstance(other, Function) and\
            self.name == other.name and\
            self.basicblocks == other.basicblocks

def get_last_instruction(target: Function) -> int:
    """ Get the index of the last instruction """
    ix = 0
    for f in functions:
        for bb in f.basicblocks:
            for i in bb.instructions:
                ix += 1
        if f.name == target.name:
            return ix

def get_last_instruction_with_bb(target: Function, target_bb: BasicBlock) -> int:
    """ Get the index of the last instruction """
    ix = 0
    for f in functions:
        for bb in f.basicblocks:
            for i in bb.instructions:
                ix += 1
            if f.name == target.name and\
               bb.name == target_bb.name:
                return ix

def get_first_instruction(target: Function) -> int:
    """ Get the index of the first instruction """
    ix = 0
    for f in functions:
        for bb in f.basicblocks:
            if f.name == target.name:
                return current_ix
            for i in bb.instructions:
                current_ix += 1

def get_location(ix: int) -> Tuple:
    """Given an index, return the function, bb, and instruction."""
    i = 0
    for f in functions:
        for bb in f.basicblocks:
            for f in bb.instructions:
                if i == ix:
                    return (f, bb, i)
                else:
                    i += 1
    raise RuntimeException(f'Index {ix} does not exist.')

# 0. Set up global objects.
#1. Open icfg
with open(args.icfg) as f:
    content = [l.strip() for l in f]

# 2. Loop to process cfg.

functions = list()
currentFunc = None
currentBB = None
i = 0
while i < len(content):
    # Functions are top level.
    if content[i].startswith('[Function'):
        # create function
        if currentFunc is not None:
            if currentBB is not None:
                currentFunc.add_basicblock(currentBB)
                currentBB = None
            functions.append(currentFunc)
            currentFunc = None
            
        content[i] = content[i].strip('[]')
        tokens = content[i].split(' ')
        currentFunc = Function(tokens[1])
        i += 1

    # Next, we expect a basic block
    elif content[i].startswith('[BB'):
        if currentFunc is None:
            raise RuntimeError(f"Got to a basic block ({content[i]}) without first "
                               "encountering a function.")
        if currentBB is not None:
            currentFunc.add_basicblock(currentBB)
            currentBB = None
            
        content[i] = content[i].strip('[]')
        tokens = content[i].split(' ')
        currentBB = BasicBlock(tokens[1])
        i += 1
    else:
        if currentBB is None:
            raise RuntimeError(f"Got to an instruction ({content[i]}) without first "
                               "encountering a basic block.")
        currentBB.add_instruction(Instruction(content[i]))
        i += 1

if currentBB is not None and currentFunc is not None:
    currentFunc.add_basicblock(currentBB)
if currentFunc is not None:
    functions.append(currentFunc)

for f in functions:
    logging.debug(f'Function {f.name} has {len(f.basicblocks)} basic blocks.')
logging.debug(f'Functions: {functions}')
# Prune any functions with 0 instructions.
i = 0
while i < len(functions):
    f = functions[i]
    if len(f.basicblocks) == 0:
        del functions[i]
    else:
        i += 1
        
# Now all of the instructions should be built. We now need to do a pass to resolve callers and callees.

# The first problem is that callers and callee nodes are on separate lines.
#  With line-based indexing, we can't have that.
#  So, we need to first remove callers and instead substitute in their edges.

# We need to do this in two passes; the first retains the name information of targets
# since edge numbers may change (since we are moving in sequential order,
# and in a single pass, the label index of the caller would never change since we're not removing past nodes.

# Since functions, basic blocks, and instructions are all in lists, their order
#  is fixed so we can use their position as the index.
calls = list() # list of tuples
succs = list()
ix = 0
for f in functions:
    for bb in f.basicblocks:
        i = 0
        while i < len(bb.instructions):
            if bb.instructions[i].content.startswith('[Caller'):
                # first, strip the instruction and replace it with
                #  the contained instruction
                tokens = bb.instructions[i].content.strip('[]').split(' ')
                inst = " ".join(tokens[1:])
                bb.instructions[i] = Instruction(inst)

                # callee information is on next line.
                try:
                    if bb.instructions[i+1].content.startswith('[Callee'):
                        callee = bb.instructions[i+1].content.strip('[]').split(' ')[1]
                        calls.append((ix, callee))
                        # Remove callee now that we've retained the information elsewhere.
                        del bb.instructions[i+1]
                except IndexError:
                    pass
                i += 1
                ix += 1
            elif bb.instructions[i].content.startswith('Successor'):
                target = bb.instructions[i].content.split(' ')[1]
                succs.append((ix-1, target))
                # remove *current node*. We won't increment i here so the next call
                # is either another successor or fails the while guard.
                del bb.instructions[i]
                logging.debug("Deleted instruction")
            else:
                i += 1
                ix += 1

logging.debug(f'Calls: {calls}')
logging.debug(f'Succs: {succs}')

# Second pass: now we will substitute the function names and basic block names
# since the index labels are fixed.
# Do the same thing for basicblocks
i = 0
while i < len(succs):
    logging.debug(f'Searching for successor edge {succs[i]}')
    target_ix = 0
    for f in functions:
        logging.debug(f'Scanning function {f.name}')
        for bb in f.basicblocks:
            # If we've found the basic block, link to the first statement
            # in it (i.e., target_ix, since only instructions have labels.)
            logging.debug(f'Scanning {bb.name}')
            if bb.name == succs[i][1]:
                logging.debug(f'Found successor {bb.name}')
                succs[i] = (succs[i][0], target_ix)
            else:
            # Appropriately increment target_ix
                for inst in bb.instructions:
                    target_ix += 1
    if not isinstance(succs[i][1], int):
        # all basic blocks should be in the CFG. So, unlike functions,
        # we should throw an exception here.
        raise RuntimeError(f'{succs[i]} was not transformed.')
    else:
        # Move pointer forward
        # this is an else because if we delete calls[i], calls[i] will now point
        #  to the next argument.
        i += 1

# Do the same for calls, except these will be a little more complicated.
i = 0
to_add = list() # maintain this list for return to call edges.
while i < len(calls):
    target_ix = 0
    for f in functions:
        # If we've found the function, link to the first statement
        # in it (i.e., target_ix, since only instructions have labels.)
        if f.name == calls[i][1]:
            calls[i] = (calls[i][0], target_ix)
            # We also want to add a call to return edge.
            # First, we need to figure out what the return instruction is.
            return_site = get_last_instruction(f)
            to_add.append((return_site, calls[i][0]))

            # # UNCOMMENT IF WE NEED TO RETURN TO THE INSTRUCTION AFTER THE CALLER
            # # Now we need to know where we're returning. Normally, this would
            # #  be the instruction after calls[i][0]. However, we need to check if
            # #  calls[i][0] is the last statement in its
            # f1, b1, i1 = get_location(calls[i][0])
            # if calls[i][0] != get_last_instruction(f, b1):
            #     # We can safely add the next instruction
            #     calls.append((return_site, calls[i][0]+=1))
            # else:
            #     # Since this is the last instruction in its basic block, we're going to
            #     #  take advantage of the succs list. We'll search for any successor
            #     #  record that has a predecessor matching calls[i][0], #
            #     #  and add that edge.
            #     for s in succs:
            #         if s[0] == calls[i][0]:
            #             to_add.append((return_site, s[1]))
                            
            # add that now since the data structure is still changing.
            # So instead, we will go through the calls later and add corresponding
            # return edges for each one.
        else:
            # Appropriately increment target_ix
            for bb in f.basicblocks:
                for inst in bb.instructions:
                    target_ix += 1
    if not isinstance(calls[i][1], int):
        # function name could not be resolved.
        logging.debug(f'Could not resolve function name {calls[i][1]}')
        del calls[i]
    else:
        # Move pointer forward
        # this is an else because if we delete calls[i], calls[i] will now point
        #  to the next argument.
        i += 1

# Finally, we can add edges in!
# First, we'll add normal edges between instructions in basic blocks.
labels = list()
edges = set()

ix = 0
for f in functions:
    for bb in f.basicblocks:
        for i in range(0, len(bb.instructions)):
            labels.append(bb.instructions[i].content)
            if (i > 0):
                edges.add((ix-1, ix))
            ix += 1

# Now, we'll just add the edges from succs and calls
edges.update(set(succs))
edges.update(set(calls))

logging.debug(f'Labels: {labels}')
logging.debug(f'Edges: {edges}')
types = ["instruction" for i in range(len(labels))]
# Add slot node inforomation
super_index = len(labels)
labels.append("<SLOT>")
types.append('supernode')
symbolcandidates = list()
classification = True if "true" in args.icfg else False
for i, v in enumerate([True, False]):
    labels.append(str(v))
    types.append('candidate')
    symbolcandidates.append({"SymbolDummyNode": i+super_index+1,
                             "SymbolName": str(v),
                             "IsCorrect": True if classification == v else False})
    edges.add((super_index, super_index+i+1))

# we always want the true candidiate first
if not symbolcandidates[0]["IsCorrect"]:
    temp = symbolcandidates[0]
    symbolcandidates[0] = symbolcandidates[1]
    symbolcandidates[1] = temp

# Add edges between supernode
if params['assert']:
    # Kill if assert is not in this graph.
    has_assert = False
    for i, l in enumerate(labels):
        if 'assert' in l.lower():
            edges.add((i, super_index))
            has_assert = True
    if not has_assert:
        logging.debug('No assert statements could be found in this program. Killing now.')
        raise RuntimeError('No assert statements present.')
else:
    for i in range(0, super_index):
        edges.add((i, super_index))

if params['label_length'] > -1:
    for i in range(super_index):
        labels[i] = labels[i][0:params['label_length']]

obj = {"ContextGraph" : {"Edges": {"Child" : sorted(list(edges))},
                         "NodeTypes": {str(i): t for i, t in enumerate(types)},
                         "NodeLabels": {str(i): v for i, v in enumerate(labels)}},
       "SlotDummyNode": super_index,
       "SymbolCandidates": symbolcandidates
}

with open(args.output, 'w') as f:
    json.dump([obj], f)
