#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, argparse, subprocess,os
from argparse import RawTextHelpFormatter
import math
import createUpgradedBuildings as BU

def parse(argv):
  #print(argv)
  parser = argparse.ArgumentParser(description="", formatter_class=RawTextHelpFormatter)
  parser.add_argument('inputfileName', )
  parser.add_argument('outputfileName', )
  
  
  if isinstance(argv, str):
    argv=argv.split()
  args=parser.parse_args(argv)
  # args.t0_buildings=args.t0_buildings.split(",")
  

  
  return(args)

        
def main(args):
  args.just_copy_and_check=True
  args.preventLinePrint=[]
  varsToValue=BU.NamesToValue(0)
  eventNameToData=BU.NamesToValue(0)
  eventNameToData.readFile(args.inputfileName,args, varsToValue)
  eventNameToData.printAll()
  with open(args.outputfileName,'w') as file:
    eventNameToData.writeEntry(file,0)
    namespace=eventNameToData.vals[0]
    for i in range(1000):
      eventNameToData.vals[1].replace("id", namespace+"."+str(i+1))
      eventNameToData.writeEntry(file,1)


if __name__ == "__main__":
  args=parse(sys.argv[1:])
  main(args)