import json
import argparse
from typing import Tuple, List
from tqdm import tqdm
import logging
logging.basicConfig(level=logging.DEBUG)
p = argparse.ArgumentParser();
p.add_argument("ast")
p.add_argument("output")
p.add_argument("-l", "--labelmode", choices=["supernode", "toplevel"],
               default="supernode", help="Whether to embed the label at the "
               "top level of the data structure, or as a supernode in the graph.")
p.add_argument("--params")
args = p.parse_args()

if args.params is None:
    transformations = {
        "slot_assert": False,
        "slot_root": False,
        "dse": False,
        "nexttoken": False,
        "hybrid_label_mode": False,
        "label_length": -1
}
else:
    with open(args.params) as f:
        transformations = json.load(f)
        
def get_node_type_and_label(line: str) -> Tuple[str, str]:
    """
    Given the string representation of a node,
    return a tuple with the type and the string name
    """
    # strip irrelevant characters
    num_spaces = get_preceding_spaces(line)
    line = line[num_spaces:]

    # the label is everything from the first quote to the end
    quote = line.find("'")
    label = line[quote:]
    line = line[:quote]

    # the type is the first string
    node_type = line.split(' ')[0]
    return (node_type, label)
    
def get_parent(ast: List[str], index: int) -> int:
    """
    Given a line, get its parent by looking for the
    closest element in the list with 2 fewer preceding spaces
    """
    num_spaces = get_preceding_spaces(ast[index])
    if num_spaces < 2:
        raise RuntimeError(f"trying to find parent of the root, file = {args.ast}")
    else:
        for i in range(index-1, -1, -1):
            if get_preceding_spaces(ast[i]) == (num_spaces - 2):
                return i
        raise RuntimeError(f"something went wrong, couldn't find the "
                           f"parent of {ast[index]} in file {args.ast}")
            

def get_preceding_spaces(line: str) -> int:
    """
    Given a line, determine the number of preceding
    "spaces" (i.e., num of characters before a letter is reached.
    """
    num_spaces = 0;
    for c in line:
        if c in ['|', ' ', '`', '-', '_']:
            num_spaces += 1
        else:
            break;
    return num_spaces


# Open ast
ast_list = list()
with open(args.ast) as f:
    for line in f:
        ast_list.append(line)

edges = list()
labels = dict()
types = dict()
# construct edges
logging.debug(f'Building ast. Number of lines: {len(ast_list)}')
parents = dict() # parents[n] stores the most recent node with n preceding spaces.
# Thus, we can do parent lookups in O(1) time instead of O(n), reducing the complexity to O(n) instead of O(n^2)
for i in tqdm(range(len(ast_list))):  # skip the root
    parents[get_preceding_spaces(ast_list[i])] = i
#    logging.debug(parents)
    if i != 0:
        try:
            edges.append( (parents[get_preceding_spaces(ast_list[i]) - 2], i) )
        except Exception as ex:
            logging.critical(f'Line: {ast_list[i]}')
            logging.critical(f'File: {args.ast}')
            raise ex
    typ, label = get_node_type_and_label(ast_list[i])
    labels[i] = label.strip()
    types[i] = typ.strip()

# add the label
ast_label = False if "false" in args.ast else True

# Compute leaf nodes
if transformations['hybrid_label_mode'] or\
   transformations['slot_assert'] or\
   transformations['nexttoken']:
    leaves = list()
    for k, _ in enumerate(labels):
        leaves.append(k)
        for e in edges:
            if e[0] == k:
                leaves.remove(k)
                break

# If this transformation is true, we replace the label of all
# non-leaf nodes with their type instead of the label.
if transformations["hybrid_label_mode"]:
    for i in range(len(labels)):
        if i not in leaves:
            labels[i] = types[i]
            
# perform transformations
if transformations["nexttoken"]:
    # add nexttoken
    nextToken = list()
    # leaf nodes will be any node with no outgoing edges
    for i in range(1, len(leaves)):
        nextToken.append([leaves[i-1], leaves[i]])
    
if args.labelmode == "supernode":
    # create super node
    super_index = len(labels)
    labels[super_index] = "<SLOT>"
    types[len(types)] = "supernode"

    # Add symbolcandidates
    symbolcandidates = list()
    supernode_edges = list()

    for i, v in enumerate([True, False]):
        labels[len(labels)] = str(v)
        types[len(types)] = "dummy"
        symbolcandidates.append({"SymbolDummyNode": i+super_index+1,
                                 "SymbolName": str(v),
                                 "IsCorrect": True if ast_label == v else False})
        supernode_edges.append((super_index, super_index+i+1))
        
    # we always want the true candidiate first
    if not symbolcandidates[0]["IsCorrect"]:
        temp = symbolcandidates[0]
        symbolcandidates[0] = symbolcandidates[1]
        symbolcandidates[1] = temp
        
    # add edges
    target = supernode_edges if transformations["dse"] else edges

    if transformations["slot_assert"]:
        # We only want an edge between the assert node and the super node.
        asserts = [i for i in range(len(labels)) if "__VERIFIER_assert" in labels[i] and i in leaves]
        if len(asserts) < 1:
            raise RuntimeError(f"{args.ast} has no assert statement")
        [target.append((a, super_index)) for a in asserts]
    elif transformations["slot_root"]:
        target.append((0, super_index))    
    else:
        # Add an edge between every node and the super node
        for i in range(0, super_index):
            target.append((i, super_index))

    if transformations['label_length'] > -1:
        for i in range(super_index):
            labels[i] = labels[i][0:transformations['label_length']]

    # output as json
    obj = {"ContextGraph" : {"Edges": {"Child" : edges, "Supernode": supernode_edges},
                             "NodeTypes": types,
                             "NodeLabels": labels},
           "SlotDummyNode": super_index,
           "SymbolCandidates": symbolcandidates
    }
    
else:
    if transformations['label_length'] > -1:
        for i in range(super_index):
            labels[i] = labels[i][0:transformations['label_length']]

    obj = {"Label" : ast_label,
           "ContextGraph" : {"Edges": {"Child" : edges},
                             "NodeTypes": types,
                             "NodeLabels": labels}
    }

if transformations["nexttoken"]:
    obj["ContextGraph"]["Edges"]["NextToken"] = nextToken

logging.debug('Writing file.')
with open(args.output, 'w') as f:
    json.dump([obj], f)
