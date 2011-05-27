#!/bin/bash

output_dir=$(dirname $0)
graph_png=$output_dir/dependencies.png
jhbuild=~/.local/bin/jhbuild

$jhbuild --moduleset=virtaal.modules dot --clusters virtaal | dot -Tpng > $graph_png && open $graph_png
