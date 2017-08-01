from collections import OrderedDict
from copy import deepcopy

import argparse
import time
import os

class Node:
    """
    Upper level node object
    
    :param left: Leaf or Node object, where path is represented as 0
    :param right: Leaf or Node object, where path is represented as 1
    :param symbol: string, stored character
    :param count: frequency of the character uncompressed string
    """
    def __init__(self, left, right, symbol, count):
        self.left = left
        self.right = right
        self.symbol = symbol
        self.count = count


class Leaf:
    """
    Bottom level node object

    :param left: Leaf or Node object, where path is represented as 0
    :param right: Leaf or Node object, where path is represented as 1
    """
    def __init__(self, symbol, count):
        self.symbol = symbol
        self.count = count


def convert_bytes(num):
    """This function will convert bytes to MB.... GB... etc"""

    for x in ('bytes', 'Kb', 'Mb', 'Gb', 'Tb'):
        if num < 1024.0:
            return '{:<5.1f}{:<2}'.format(num, x)
        num /= 1024.0


def create_queue(string):
    """
    Sorts characters based on their frequency

    :param string: uncompressed string
    :returns: sorted array of Leaf objects with each character and count from 'string'
    """
    counter = OrderedDict()
    for c in string:
        if c in counter:
            counter[c] += 1
        else:
            counter[c] = 1

    return sorted([Leaf(k, v) for k, v in counter.items()], key=lambda x: x.count)


def create_tree(queue):
    """
    Create pseudo binary tree from array of nodes

    Procedure:
    - While there is more than one node in the queue:
    - Remove the two nodes of highest priority (lowest probability) from the queue
    - Create a new node with these two nodes as children and with
      probability equal to the sum of the two nodes' probabilities.
    - Add the new node to the queue.

    :param queue: array of Leaf objects
    :returns: Node object which is the root of the binary tree
    """
    queue = deepcopy(queue)

    while len(queue) > 1:
        l = queue.pop(0)
        r = queue.pop(0)

        new_node = Node(l, r, l.symbol + r.symbol, l.count + r.count)

        for i in range(len(queue)):
            if new_node.count < queue[i].count:
                queue.insert(i, new_node)
                break

        else:
            queue.append(new_node)

    return queue[0]


def byte_string_generator(byte_string):
    pos = 0
    length = len(byte_string) - 1

    while pos <= length:
        if length - pos < 8:
            yield byte_string[pos:] + '0' * (7 - (length % 8))
        else:
            yield byte_string[pos:pos+8]

        pos += 8


def create_metadata(queue, padding):
    """
    Encodes the queue into a bytearray for reconstructing the huffman tree 
    The first byte tells the amount of padding bits on the left side of the file
    the next byte is the pair count, which is then followed by a 5 byte pair
    
    Each pair is stored in the order of lowest frequency to highest
    Each key is the 8 bit ascii value of the character and its frequency is stored as a 32 bit unsigned integer

    [  5  ] [  2  ] [  a  ] [   295   ] [  b  ] [   30   ]
    ^-----^ ^-----^ ^-----^ ^---------^
    padding  count   8bits    32bits

    :param queue: list of Leaf objects
    :returns: bytearray
    """
    b = bytearray()

    # store the padding
    b.append(padding)

    # store pair count
    b.append(len(queue))

    for node in queue:
        b.append(ord(node.symbol))

        for i in (24, 16, 8, 0):
            b.append(node.count >> i & 0xff)

    return b


def read_metadata(byte_string):
    """
    Count the amount of key pairs and create a queue
    
    :param byte_string: byte string of 'compressed' text
    :returns: list of Node objects and padding
    """
    padding = byte_string[0]
    pairs = byte_string[1]
    queue = []

    for i in range(pairs):
        # each pair is 5 bytes, so index is multiplied by 5
        # 2 is added because the two first bytes are skipped
        symbol = chr(byte_string[i * 5 + 2])

        count = 0
        for j in range(i * 5 + 3, i * 5 + 7):
            count = count << 8 ^ byte_string[j]

        queue.append(Leaf(symbol, count))

    return queue, padding


def write_bytes(byte_string, metadata, output_name):
    """
    :param byte_string: byte string of 'compressed' text
    :param metadata: bytearray representing metadata
    :param output_name: name of the output file
    """
    gen = byte_string_generator(byte_string)

    byte_array = bytearray()
    byte_array.extend(metadata)

    for bits in gen:
        # big-endian bits[::-1]
        # little-endian? 
        byte_array.append(int(bits[::-1], 2))

    with open(os.getcwd() + '\\{}.bin'.format(output_name), 'wb') as f:
        f.write(byte_array)


def parse_string(string, tree):
    """
    'Compresses' the given string by using a lookup table to translate each character 
    into its binary path

    :param string: uncompressed string
    :param tree: Node object which represents the root of the binary tree
    :returns: Dict where each key value is a character with its value 
              being the string representation of its binary path

          a
          |
       -------
       | 0   | 1
       b       c
    -------
    | 0   | 1
    d     e

    >> {b: '0', c: '1', d: '00', e: '01'}
    """
    lookup_table = {}
    search(tree, '', lookup_table)

    return ''.join([lookup_table[c] for c in string])


def search(current_node, path, lookup_table):
    """
    Recursively search paths of the given tree and add them to the lookup table

    :param current_node: Node or Leaf object 
    :param path: string representation of a binary path
    :param lookup_table: reference to the lookup table dict
    """
    if isinstance(current_node, Leaf):
        lookup_table[current_node.symbol] = path
    else:
        search(current_node.left, path + '0', lookup_table)
        search(current_node.right, path + '1', lookup_table)


def byte_array_gen(byte_array, start_pos, end_padding):
    pos = start_pos

    end_pos = len(byte_array)
    # last byte gets handled differently if there is padding
    end_pos = end_pos - 1 if end_padding else end_pos

    while pos < end_pos:
        byte = '{:0>8}'.format(bin(byte_array[pos])[2:])
        
        # big endian????
        byte = byte[::-1]
        
        for bit in byte:
            yield bit
        
        pos += 1

    # if last byte contains padding, remove the trailing 0's
    if end_padding:
        byte = '{:0>8}'.format(bin(byte_array[pos])[2:])
        byte = byte[:end_padding-1:-1]

        for bit in byte:
            yield bit


def uncompress(filename, output):
    """
    Decompresses .bin file into a .txt file by reconstructing the huffman tree
    from the metadata at the start of the file and tracing a path to each character
    
    :param filename: name of the input file
    :param output: name of the output file
    """
    characters = []

    with open(filename, 'rb') as f:
        byte_array = f.read()

    queue, end_padding = read_metadata(byte_array)

    # create a generator object for retrieving bits
    start_pos = len(queue) * 5 + 2
    gen = byte_array_gen(byte_array, start_pos, end_padding)

    tree = create_tree(queue)

    current_node = tree

    for c in gen:
        if isinstance(current_node, Leaf):
            characters.append(current_node.symbol)

            # go back to root node
            if c == '1':
                current_node = tree.right
            else:
                current_node = tree.left
        else:
            if c == '1':
                current_node = current_node.right
            else:
                current_node = current_node.left

    with open(os.getcwd() + '\\{}.txt'.format(output), 'w') as f:
        f.write(''.join(characters))


def compress(filename, output):
    """
    Compresses text by creating a huffman tree and writing it to a .bin file
    
    :param filename: name of the input file
    :param output: name of the output file
    """
    with open(filename, 'r') as f:
        string = ''.join(f.readlines())        

    queue = create_queue(string)

    tree = create_tree(queue)
    byte_string = parse_string(string, tree)

    metadata = create_metadata(queue, 7 - (len(byte_string) % 8))
    write_bytes(byte_string, metadata, output)


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('output_name', nargs='?', default='output')
    parser.add_argument('-x', '--extract', dest='extract', action='store_true')
    return parser.parse_args()


def main():
    args = get_arguments()

    # for timing the process
    prev = time.time()

    if args.extract:
        print('Extracting {} into {}.txt'.format(args.filename, args.output_name))
        uncompress(args.filename, args.output_name)
    else:
        print('Compressing {} into {}.bin'.format(args.filename, args.output_name))
        compress(args.filename, args.output_name)
    
    print('[done {:.2f}s]'.format(time.time() - prev))

    
if __name__ == '__main__':
    main()
