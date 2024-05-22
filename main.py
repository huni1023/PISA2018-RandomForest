import os
import argparse
from src.load import Load
from src.eda import main
from huniutils.manage_os import check_prerequisite_dir

App_dir = os.path.dirname(os.path.realpath(__file__))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action="store_true",
                        help="init project, create required folder")
    parser.add_argument('--load', action="store_true",
                        help="load data and filter nation")
    
    parser.add_argument('--eda', action="store_true",
                        help="exploratory data analysis")
    parser.add_argument('--PV', action='store',
                        help="run eda by each PV")
    parser.add_argument('--loop', action='store_true',
                        help="run eda on all PVs")
    parser.add_argument('--visualize', action='store_true',
                        help="decide visualize or not")

    args = parser.parse_args()
    
    if args.init:
        check_prerequisite_dir(App_dir,
                               ['data', 'logs', 'result'])
    
    if args.load:
        Loader = Load(codeBook='codebook.xlsx')
        Loader.defaultCleaner()

    if args.eda:
        if args.PV is not None:
            assert (int(args.PV) < 11) and (int(args.PV) > 0), f"invalid argument PV, only 1 to 10 is allowed"
            if args.visualize:
                main(int(args.PV), True)
            else:
                main(int(args.PV), False)
        
        if args.loop:
            for idx in range(1, 11):
                if args.visualize:
                    main(idx, True)
                else:
                    main(idx, False)