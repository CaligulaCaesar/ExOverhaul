#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, argparse, subprocess,os
from argparse import RawTextHelpFormatter
import math
import copy
import io
import codecs
import glob
from shutil import copyfile

def parse(argv):
  parser = argparse.ArgumentParser(description="From any file containing buildings, creates a new file that allow the direct construction of upgraded buildings while keeping costs correct and ensuring uniquness of unique buildings.\n\nIMPORTANT: If you apply this script to one building file, you need to also apply it to all building file with buildings you depend on (e.g. via 'has_building').\nBuildings need to be sorted by tier!\n\nLower tier versions will be removed if higher tier is available (unless specified otherwise).\nCosts and building times will be added up (with optional discount).\nFurthermore copies icons and descriptions if according folder and file is given.\nThis mod will slightly increase the costs for every building that has a 'tier0' version as those costs are now added to the 'direct construction tier1' version as for every other building. This means those 'tier0' are no waste of resources anymore!\n\nImportant info regarding building file formatting: No 'xyz= newline {'. Open new blocks via 'xyz={ newline' as Paradox seems to have always done in their files. Limitation: Empire unique buildings will never get a direct_build copy (otherwise they would lose uniqueness)!", formatter_class=RawTextHelpFormatter)
  parser.add_argument('buildingFileNames', nargs = '*', help='File(s)/Path(s) to file(s) to be parsed or .mod file (see "--create_standalone_mod_from_mod). Output is named according to each file name with some extras. Globbing star(*) can be used (even under windows :P)')
  parser.add_argument('-l','--languages', default="braz_por,english,french,german,polish,russian,spanish", help="Languages for which files should be created. Comma separated list. Only creates links to existing titles/descriptions (but needs to do so for every language)(default: %(default)s)")
  parser.add_argument('-k','--keep_lower_tier', action="store_true", help="Does not change any building requirements. Changing of building requirements only works with regard to capital buildings and techs and will fail if any of those are negated within the original conditions")
  parser.add_argument('-s','--t0_buildings', default='building_colony_shelter,building_deployment_post,building_basic_power_plant,building_basic_farm,building_basic_mine', help="Does not change building requirements for buildings in this comma separated list. Furthermore, their cost will not be added to the t1 buildings (but deducted from the upgrade version) (default: %(default)s)")
  parser.add_argument('-t','--time_discount', default=0.25, type=float, help="Total time of tier n will be: Time(tier n-1)+Time(upgrade tier n)*(1-discount), with the restriction that total time will never be lower than 'Time(upgrade tier n)' (default: %(default)s)")
  parser.add_argument('-c','--cost_discount', default=0, type=float, help="Total cost of tier n will be: Cost(tier n-1)+Cost(upgrade tier n)*(1-discount), with the restriction that total cost will never be lower than 'Cost(upgrade tier n)'(default: %(default)s)")
  parser.add_argument('-f','--just_copy_and_check', action="store_true", help="If any non-building file in your mod includes 'has_building' mentions on buildings that will be copied by this script, run this mode once with all such files as input instead of the building files. In this mode the script will simply replace all 'has_building = ...' with scripted_triggers also checking for direct_build versions. You need to apply the main script FIRST!")
  parser.add_argument('-o','--output_folder', default="build_upgraded", help="(default: %(default)s)")
  parser.add_argument('--replacement_file', default="", help="Executes a very basic conditional replace on buildings. Example: 'IF unique in buildingName and is_listed==no newline	ai_weight = { weight = @crucial_2 }': For all buildings that have 'unique' in their name and are not listed, set ai_weight to given value. Any number of such replaces can be in the file. An 'IF' at the very start of a line starts a replace. the next xyz = will be the tag used for replacing. You can also start a line with 'EVAL' instead of 'IF' to write an arbitrary condition. You need to know the class structure for this though.")
  parser.add_argument('-j','--join_files', action="store_true", help="Output from all input files goes into a single file. Has to be activated if you have upgrades distributed over different files. Will not copy comments!")
  parser.add_argument('-r','--remove_reduntant_upgrades', action="store_true", help="Removes all upgrades where the building can also be reached differently.")
  parser.add_argument('-g','--gameVersion', default="1.8.*", help="Game version of the newly created .mod file to avoid launcher warning. Ignored for standalone mod creation. (default: %(default)s)")
  parser.add_argument('--tags', default="buildings", help="Comma separated list of tags. Ignored for standalone mod creation.")
  parser.add_argument('--picture_file', default="", help="Picture file set in the mod file. Ignored for standalone mod creation. This file must be manually added to the mod folder!")
  parser.add_argument('--load_order_priority', action="store_true", help="If enabled, mod will be placed first in mod priority by adding '!' to filename. This allows the construction of mod extensions. Alternatively, you can create a standalone version , see '--create_standalone_mod_from_mod'.")
  parser.add_argument('-m','--create_standalone_mod_from_mod', action="store_true", help="If this flag is set, the script will create a copy of a mod folder, changing the building files and has_building triggers. Main input of the script should now be the .mod file.")
  parser.add_argument('--custom_mod_name', help="If set, this will be the name of the new mod")
  parser.add_argument('--create_tier5_enhanced',action='store_true', help=argparse.SUPPRESS)

  
  if isinstance(argv, str):
    argv=argv.split()
  args=parser.parse_args(argv)

  args.t0_buildings=args.t0_buildings.split(",")
  
  return(args)

class NamesToValue: #Basically everything is stored recursively in objects of this class. Each file is one such object. Each tag within is one such object. The variables defined in a file are one such object. Only out-of-building comments are ignored and simply copied file to file.
  def __init__(self,level):
    self.names=[]
    self.vals=[]
    self.comments=[]
    self.bracketLevel=level
  def get(self,name): #allows changing of content if vals[i] is an object
    return self.vals[self.names.index(name)]
  def getOrCreate(self,name): #required to add something a a category that may already exist "getOrCreate(name).add..."
    if not name in self.names:
      self.add2(name, NamesToValue(self.bracketLevel+1))
    return self.vals[self.names.index(name)]
  def getAll(self):
    return [[self.names[i],self.vals[i]] for i in range(len(self.names))]
  def insert(self,array,index): #insert via index
    self.names[index:index]=[array[0].strip()]
    val=array[1]
    self.vals[index:index]=[val]
    if len(array)>2:
      comment=array[2]
    else:
      comment=""
    self.comments[index:index]=[comment]
  def add(self,array): #add a 2-size array
    self.names.append(array[0].strip())
    val=array[1]
    self.vals.append(val)
    if len(array)>2:
      comment=array[2]
    else:
      comment=""
    self.comments.append(comment)
  def add2(self,name,val, comment=''): #add via two separate pre-formated variables
    self.names.append(name)
    self.vals.append(val)
    self.comments.append(comment)
  def addString(self, string): #add via raw data. Only works for lines that are bracketClosed within
    array=string.split("=")
    array[1:]=["=".join(array[1:]).strip()]
    indexComment=array[1].find("#")
    if indexComment>0:
      comment=array[1][indexComment:]
      array[1]=array[1][:indexComment]
      array.append(comment)
    self.add(array)
  def remove(self, name): #remove via name
    i=self.names.index(name)
    self.removeIndex(i)
  def removeIndex(self, i): #remove via name
    del self.names[i]
    del self.vals[i]
    del self.comments[i]
  def replace(self, name,val,comment=''): #replace via name
    i=self.names.index(name)
    self.vals[i]=val
    self.comments[i]=comment
  def splitToListIfString(self,name): #I do not generally split lines that open and close brackets within the line (to prevent enlarging the file). Yet sometimes it's necessary...
    try:
      i=self.names.index(name)
    except ValueError:
      return NamesToValue(0)
    if not isinstance(self.vals[i],NamesToValue):
      string=self.vals[i].strip()
      if string[0]=="{":
        string=string[1:-1].strip() #remove on bracket layer
      self.vals[i]=NamesToValue(self.bracketLevel+1)
      if len(string)>0:
        self.vals[i].addString(string)
    return self.vals[i]
  def increaseLevelRec(self): #increase the bracket level for this object and every object below. Beware that as the head name of this object is stored one level higher, the head name of the object is not shifted
    self.bracketLevel+=1
    for val in self.vals:
      if isinstance(val, NamesToValue):
        val.increaseLevelRec()
  def printAll(self): #primitive print. Just for testing
    for i in range(len(self.names)):
      for b in range(self.bracketLevel):
        print("\t",end="")
      if not isinstance(self.vals[i],NamesToValue):
        print(self.names[i],end="")
        if len(self.vals[i])>0:
          print(" = "+self.vals[i],end="")
      else:
        if self.bracketLevel==1:
          print("\n",end="")
          for b in range(self.bracketLevel):
            print("\t",end="")
        print(self.names[i]+" = {\n",end="")
        self.vals[i].printAll()
        for b in range(self.bracketLevel):
          print("\t",end="")
        print("}",end="")
      print(self.comments[i],end="")
      print("\n",end="")
  def writeAll(self,file): #formatted writing. Paradox style minus most whitespace tailing errors
    for i in range(len(self.names)):
      for b in range(self.bracketLevel):
        file.write("\t")
      if not isinstance(self.vals[i],NamesToValue):
        file.write(self.names[i])
        if len(self.vals[i])>0:
          file.write(" = "+self.vals[i])
      else:
        if self.bracketLevel==1:
          file.write("\n")
          for b in range(self.bracketLevel):
            file.write("\t")
        file.write(self.names[i]+" = {\n")
        self.vals[i].writeAll(file)
        for b in range(self.bracketLevel):
          file.write("\t")
        file.write("}")
      file.write(self.comments[i])
      file.write("\n")
  def replaceAllHasBuildings(self, copiedBuildings): #"has_building=" fails working if different version of the same building exist (Paradox should have realised this on creation of machine empire capital buildings but they didn't... They simply created very lengthy conditions. Shame...). We replace them by scripted_triggers. Due to cross-reference in between files I do this for EVERY building, even the ones I did not copy.
    for i in range(len(self.names)):
      if isinstance(self.vals[i], NamesToValue):
        self.vals[i].replaceAllHasBuildings(copiedBuildings)
      elif self.names[i]=="has_building" and self.vals[i]!="no":
        if self.vals[i].strip('"') in copiedBuildings:
          self.names[i]="has_"+(self.vals[i].replace('"',''))
          self.vals[i]="yes"
      else: #find hidden "has_building"
        index=0
        while index>=0 and (self.vals[i].find("has_building ",index)!=-1 or self.vals[i].find("has_building=",index)!=-1):# and self.vals[i].find("has_building = no")==-1:
          index=max(self.vals[i].find("has_building ",index),self.vals[i].find("has_building=",index))        #find one that is not -1
          #hidden one must have two brackets around. find those
          leftBracked=self.vals[i].rfind("{",0,index)
          rightBracked=self.vals[i].find("}",index)
          toBeReplaced=self.vals[i][leftBracked:rightBracked+1]
          # print(leftBracked)
          # print(rightBracked)
          # print(self.vals[i])
          # print(index)
          # print(self.vals[i][index])
          # print(toBeReplaced)
          buildingName=toBeReplaced.split("=")[1].replace("}","").replace('"','').strip()
          if buildingName in copiedBuildings:
            self.vals[i]=self.vals[i].replace(toBeReplaced,"{ has_"+buildingName+" = yes }")
            # print(toBeReplaced)
            
          index+=1 #prevent finding the same has_building again!
  def removeDuplicatesRec(self):
    # try :
      # print(self.buildingName)
    # except AttributeError:
      # pass
    duplicates=[]
    for i in range(len(self.names)):
      if i in duplicates:
        continue
      for j in range(i+1, len(self.names)):
        if j in duplicates:
          continue
        if self.names[i]==self.names[j]:
          if isinstance(self.vals[i],NamesToValue):
            if isinstance(self.vals[j],NamesToValue):
              if self.vals[i].compare(self.vals[j]):
                duplicates.append(j)
          else:
            if self.vals[i]==self.vals[j]: #string compare (or string vs object which gives correct 0)
              duplicates.append(j)
    for i in reversed(sorted(duplicates)):      #delete last first to make sure indices stay valid
      # self.printAll()
      self.removeIndex(i)
    for i in range(len(self.names)): #recurively through remaining elements
      if isinstance(self.vals[i], NamesToValue):
        self.vals[i].removeDuplicatesRec()
  def compare(self, other):
    if len(self.names)!=len(other.names):
      return 0
    for i in range(len(self.names)):
      if self.names[i]!=other.names[i]:
        return 0
      if isinstance(self.vals[i],NamesToValue):
        if isinstance(other.vals[i],NamesToValue):
          if not self.vals[i].compare(other.vals[i]):
            return 0
        else:
          return 0
      else:
        if self.vals[i]!=other.vals[i]:
          return 0
    return 1
  def removeDuplicateNames(self):
    duplicates=[]
    for i in range(len(self.names)):
      if i in duplicates:
        continue
      for j in range(i+1, len(self.names)):
        if j in duplicates:
          continue
        if self.names[i]==self.names[j]:
          duplicates.append(j)
    for i in reversed(sorted(duplicates)):      #delete last first to make sure indices stay valid
      self.removeIndex(i)
      
class Building(NamesToValue): #derived from NamesToValue with four extra variables and a custom initialiser. Stores main tag of each building (and the reduntantly stored building name)
  def __init__(self, lineNbr,buildingName):
    self.names=[]
    self.vals=[]
    self.comments=[]
    self.bracketLevel=1
    self.lineStart=lineNbr#line start in original file
    self.lineEnd=lineNbr #line end in original file
    self.lowerTier=0
    self.buildingName=buildingName
    self.wasVisited=0
 
def computeNewCosts_Part1(buildingData, upgradeData, args, varsToValue, t1Costfix=False):
  #compute build times
  computeNewCosts(buildingData, upgradeData, "base_buildtime", args.time_discount,varsToValue, t1Costfix)
  
  #compute costs
  costsA=buildingData.splitToListIfString("cost")
  costsB=upgradeData.splitToListIfString("cost")
  allCostNames=list(set(costsA.names)|set(costsB.names)) #create a list that includes any cost name from either building exactly once
  for name in allCostNames:
    if name[0]!="#":
      computeNewCosts(costsA, costsB, name, args.cost_discount,varsToValue, t1Costfix) 
  
def computeNewCosts(entryA, entryB, tag, discount, varsToValue, t1Costfix=False):
  # magnitude=[entryA.get(tag), entryB.get(tag)]
  magnitude=[]
  try:
    magnitude.append(entryA.get(tag))
  except ValueError:
    magnitude.append("0")  
  try:
    magnitude.append(entryB.get(tag))
    B=1
  except ValueError:
    magnitude.append("0")
    B=0
  for i in range(len(magnitude)):
    if magnitude[i][0]=="@":
      magnitude[i]=varsToValue.get(magnitude[i])
    magnitude[i]=float(magnitude[i])
  if t1Costfix:
    finalVal=int((magnitude[1]-magnitude[0])/(1-discount)) #Making sure the the new t1 "direct build" will have the same costs as in the original version where t1 was also direct build. The t1 upgrade version on the other hand will be cheaper now!
  else:
    finalVal=int(magnitude[0]+(1-discount)*magnitude[1]) #TODO possibly you would want some rounding here
    if (finalVal<magnitude[1]):
      finalVal=int(magnitude[1])
    
  finalVal=str(finalVal)
  if B:
    entryB.replace(tag,finalVal)
  else:
    entryB.add([tag, finalVal])

def attemptGet(building, tag): 
  try:
    return building.get(tag)
  except ValueError:
    return NamesToValue(0) #empty list
    
def main(args, allowRestart=1):   
  scriptDescription='#This file was created by script!\n#Instead of editing it, you should change the origin files or the script and rerun the script!\n#Python files that can be directly used for a rerun (storing all parameters from the last run) should be in the main directory\n'

  if not args.create_standalone_mod_from_mod or not args.just_copy_and_check:
    if not os.path.exists(args.output_folder+"/common"):
      os.mkdir(args.output_folder+"/common")
    if not os.path.exists(args.output_folder+"/common/buildings"):
      os.mkdir(args.output_folder+"/common/buildings")  
    if not os.path.exists(args.output_folder+"/common/scripted_triggers"):
      os.mkdir(args.output_folder+"/common/scripted_triggers")
    
  copiedBuildingsFileName=args.output_folder+"/copiedBuildings.txt"
  try: 
    with open(copiedBuildingsFileName) as file:
      copiedBuildings=[line.strip() for line in file]
  except FileNotFoundError:
    copiedBuildings=[]
  if not args.just_copy_and_check:
    copiedBuildingsFile=open(copiedBuildingsFileName,'w')
  globbedList=[]
  for b in args.buildingFileNames:
    globbedList[0:0]=glob.glob(b)
  fileIndex=-1
  for buildingFileName in globbedList:#args.buildingFileNames:
    fileIndex+=1
    #READ FILE
    if fileIndex==0 or not args.join_files:
      varsToValue=NamesToValue(0)
      buildingNameToData=NamesToValue(0)
    bracketLevel=0
    objectList=[] #objects currently open objectList[0] would be lowest bracket object (a building), etc
    with open(buildingFileName,'r') as inputFile:
      print("Start reading "+buildingFileName)
      if args.just_copy_and_check:
        if args.create_standalone_mod_from_mod:
          outPath=args.output_folder
        else:
          outPath=args.output_folder+"/common/scripted_triggers/"
      else:
        outPath=args.output_folder+"/common/buildings/"
      if not args.just_copy_and_check or not args.create_standalone_mod_from_mod:
        with open(outPath+os.path.basename(inputFile.name),'w') as outputFile:
          outputFile.write(scriptDescription)
          outputFile.write("#overwrite\n")
      lineIndex=0
      for line in inputFile:
        lineIndex+=1
        line=line.strip()
        if len(line)>0 :
          if line[0]=="@":
            varsToValue.addString(line)
          elif line[0]!="#" or bracketLevel>0:
            bracketOpen=line.count("{")
            bracketClose=line.count("}")
            if bracketLevel==0:
              if (bracketOpen!=1 or bracketClose!=0) and not args.just_copy_and_check:
                print("Error in line {!s}:\n{}\nInvalid building start line".format(lineIndex,line))
                sys.exit(1)
              buildingName=line.split("=")[0].strip()
              objectList.append(Building(lineIndex,buildingName))
              buildingNameToData.add2(buildingName,objectList[-1])
            else:
              if bracketOpen>bracketClose:
                newObject=NamesToValue(bracketLevel+1)
                objectList[-1].add([line.split("=")[0],newObject])
                objectList.append(newObject)
              elif bracketOpen==bracketClose:
                objectList[-1].addString(line)
              
            bracketLevel+=bracketOpen
            bracketLevel-=bracketClose
            if bracketLevel==0 and bracketClose>0:
              buildingNameToData.vals[-1].lineEnd=lineIndex
            objectList=objectList[0:bracketLevel]
    #END OF READ FILE
    if args.join_files:
      if fileIndex<len(globbedList)-1:
        continue
      else:
        varsToValue.removeDuplicateNames()
        
    if args.remove_reduntant_upgrades:
      for buildingData in buildingNameToData.vals:
        #print(len(buildingNameToData.vals))
        #print(buildingData.buildingName)
        upgrades=buildingData.splitToListIfString("upgrades")
        #print(upgrades.names)
        upgradeIndex=-1
        while 1:
          upgradeIndex+=1
          if upgradeIndex>=len(upgrades.names):
            break
          if len(upgrades.names[upgradeIndex])>0:
            upgradeList=[buildingNameToData.get(upgrades.names[upgradeIndex])]
            upgrade=upgradeList[0]
            while len(upgradeList)>0:
              upgradeList=upgradeList[1:]
              for upgradeName in upgrade.splitToListIfString("upgrades").names:
                if len(upgradeName)>0:
                  upgradeList.append(buildingNameToData.get(upgradeName))
              if len(upgradeList)==0:
                break
              upgrade=upgradeList[0]
              # print(upgrades.names)
              # print(upgrade.buildingName)
              if upgrade.buildingName in upgrades.names:
                #print(upgrades.names)
                upgrades.names.remove(upgrade.buildingName)
                #print(upgrades.names)
              
              
            
      
    
    if not args.just_copy_and_check:  
      #COPY AND MODIFY WHERE NEEDED       
      buildingNameToDataOrigVals=copy.copy(buildingNameToData.vals) #shallow copy of the buildings: buldingNameToData.vals will later be changed (a lot). Most of these changes reflect in buildingNameToDataOrigVals, except that new entries in the array do not appear!
      triggers=NamesToValue(0) #list of scripted_triggers later to be saved in a file
      locData=[] #list of localisation links later to be saved in a file. One of the few times NamesToValue class is NOT used
      for origBuildI in range(len(buildingNameToDataOrigVals)): #iterate through lowest tier buildings. Higher tier buildings will be ignored (via "is_listed = no",which is even set for tier 1 if tier 0 exists)
        baseBuildingData=buildingNameToDataOrigVals[origBuildI] #data of the lowest tier building
        if "is_listed" in baseBuildingData.names and baseBuildingData.get("is_listed")=="no":
          continue
        #triggers.add2("has_"+baseBuildingData.buildingName,"{ has_building = "+baseBuildingData.buildingName+" }")   #redundant but simplifies later replaces
        triggerIndexAtStart=len(triggers.names) #later used together with "baseBuildingData" to determine what buildings are checked for if planet_unique
        
        #ITERATE THROUGH WHOLE BUILDING TREE/LINE
        buildingDataList=[baseBuildingData]
        while len(buildingDataList)>0 and "upgrades" in buildingDataList[0].names: #starting with the lowest tier building we iterate through every single descendent. Upgrade loops would obviously kill the script at this point :P
          #take first element to work with and remove it from todo-list
          buildingData=buildingDataList[0]
          buildingDataList=buildingDataList[1:]
          upgrades=buildingData.splitToListIfString("upgrades")
          # upgrades=buildingData.get("upgrades")
          # if not isinstance(upgrades,NamesToValue):
            # buildingData.replace("upgrades",NamesToValue(buildingData.bracketLevel+1))
            # buildingData.get("upgrades").addString(upgrades.replace("{","").replace("}","").strip())
            # upgrades=buildingData.get("upgrades")
          
          #new building requirements to ensure that only the highest currently available is buildable. Keep the building list as short as possible. Done via "potential" to compeltely remove them from the list (not even greyed out)
          newRequirements=NamesToValue(2)
          if len(upgrades.names)>0 and not args.keep_lower_tier and not buildingData.buildingName in args.t0_buildings:
            buildingData.getOrCreate("potential")
            buildingData.splitToListIfString("potential").add(["NAND", newRequirements])
           
          #iterate through all upgrades: Create a copy of each upgrade, compute costs. Finish requirements for current building and add the copies to the todo-list
          for upgradeName in upgrades.names:
            try:
              upgradeData=buildingNameToData.get(upgradeName) #allow editing
            except ValueError:
              print("WARNING: Upgrade building not found for {}. Either missing or in different file. Cannot apply script to this! In different file will work with '--join_files' option.".format(buildingData.buildingName))
              if "planet_unique" in buildingData.names:
                print("EXTRA WARNING: The problematic building is planet_unique. This error might destroy uniqueness!")
              continue
            if upgradeData.wasVisited:
              print("Script tried to visit "+upgradeData.buildingName +" twice (second time via "+buildingData.buildingName+"). This is to be expected if different buildings upgrade into this building, but could also indicate an error in ordering: Of all 'is_listed=yes' buildings in a tree, the lowest tier must always be first!")
            elif buildingData.buildingName in args.t0_buildings: #don't do if visited twice!
              computeNewCosts_Part1(buildingData, upgradeData, args, varsToValue, True) #fix t0-t1 costs
              
            #this is a higher tier building. If there is no pure upgrade version yet, create it now. A direct build one will be created anyway!
            if not "is_listed" in upgradeData.names:
              upgradeData.add2("is_listed","no")
            if upgradeData.get("is_listed")=="yes":
              upgradeData.replace("is_listed","no")
            upgradeData.wasVisited=1
            
              
              
            origUpgradeData=upgradeData  
            upgradeData=copy.deepcopy(buildingNameToData.get(upgradeName)) #now copy to prevent further editing
            
            if "empire_unique" in upgradeData.names and upgradeData.get("empire_unique")=="yes":
              #triggers.add2("has_"+upgradeName,"{ has_building = "+upgradeName+" }")   #redundant but simplifies later replaces
              continue #do not copy empire_unique buildings EVER. Impossible to keep them unique otherwise, for some reason even if capital only

            #new requirements: Only buildable if one of the conditions of the next higher tier is not satisfied.
            poss=copy.deepcopy([upgradeData.splitToListIfString("prerequisites"),upgradeData.splitToListIfString("potential"),upgradeData.splitToListIfString("allow")])
            for eI in range(len(poss[0].names)):
              poss[0].vals[eI]='{ has_technology ='+' {} '.format(poss[0].names[eI])+'}'
              poss[0].names[eI]='owner'
            for p in poss:
              for e in p.getAll():
                newRequirements.add(e)
            
            
            
            upgradeBuildingIndex=buildingNameToData.names.index(upgradeName) #index of 'upgradeData' building in the list of all buildings (including already copied buildings)
            buildingNameToData.insert([upgradeName,upgradeData],upgradeBuildingIndex) #insert the copy before 'upgradeData'. upgradeBuildingIndex is now the index of the copy!
            buildingNameToData.vals[upgradeBuildingIndex].remove("is_listed") #removing "is_listed = no"
            if args.create_tier5_enhanced and buildingData.buildingName.replace("_direct_build","")[-3:]=="_rw":
              rw_upgrade_building=copy.deepcopy(buildingNameToData.get(upgradeName))
              rw_upgrade_building.buildingName+="_rw"
              adjacency_bonus=rw_upgrade_building.splitToListIfString("adjacency_bonus")
              potential_rw=rw_upgrade_building.splitToListIfString("potential")
              potential_rw.addString("planet = { is_ringworld_or_machine_world = yes }")
              for adI in range(len(adjacency_bonus.vals)):
                adjacency_bonus.vals[adI]=str(int(adjacency_bonus.vals[adI])+1)
              buildingData.splitToListIfString("upgrades").remove(upgradeName)
              buildingData.splitToListIfString("upgrades").addString(rw_upgrade_building.buildingName)
              buildingData_no_direct_build=buildingNameToData.get(buildingData.buildingName.replace("_direct_build",""))
              buildingData_no_direct_build.splitToListIfString("upgrades").remove(upgradeName)
              buildingData_no_direct_build.splitToListIfString("upgrades").addString(rw_upgrade_building.buildingName)
              
              buildingNameToData.names[upgradeBuildingIndex]+="_rw"
              adjacency_bonus=buildingNameToData.vals[upgradeBuildingIndex].splitToListIfString("adjacency_bonus")
              potential_rw=buildingNameToData.vals[upgradeBuildingIndex].splitToListIfString("potential")
              potential_rw.addString("planet = { is_ringworld_or_machine_world = yes }")
              
              newList=NamesToValue(1)
              newList.getOrCreate("OR").add2("has_building",upgradeName+"_rw") #creates the "OR" and fills it with the first entry
              newList.get("OR").add2("has_building",upgradeName+"_rw_direct_build") #second entry to "OR"
              triggers.add2("has_"+upgradeName+"_rw", newList)
              copiedBuildingsFile.write(upgradeName+"_rw"+"\n")
              for adI in range(len(adjacency_bonus.vals)):
                adjacency_bonus.vals[adI]=str(int(adjacency_bonus.vals[adI])+1)
                
              buildingNameToData.insert([rw_upgrade_building.buildingName, rw_upgrade_building], upgradeBuildingIndex+1) #insert after _direct_build_rw version
              
            buildingNameToData.names[upgradeBuildingIndex]+="_direct_build" #renaming (as internal name needs to be unique. Not visible in-game
            buildingNameToData.vals[upgradeBuildingIndex].buildingName=buildingNameToData.names[upgradeBuildingIndex]
            buildingNameToData.vals[upgradeBuildingIndex].lowerTier=buildingData #lower Tier will later be used to ensure uniqueness of unique buildings
            
            #create a new scripted_trigger, consisting of both the original upgrade and the copy that can be directly build
            if not args.create_tier5_enhanced or buildingData.buildingName.replace("_direct_build","")[-3:]!="_rw":
              newList=NamesToValue(1)
              newList.getOrCreate("OR").add2("has_building",upgradeName) #creates the "OR" and fills it with the first entry
              newList.get("OR").add2("has_building",buildingNameToData.names[upgradeBuildingIndex]) #second entry to "OR"
              triggers.add2("has_"+upgradeName, newList)
              copiedBuildingsFile.write(upgradeName+"\n")
            
            #REMOVE COPY FROM TECH TREE. Seems to remove the copy completely :( Pretty useless trigger...
            if "show_tech_unlock_if" in buildingNameToData.vals[upgradeBuildingIndex].names:
              buildingNameToData.vals[upgradeBuildingIndex].remove("show_tech_unlock_if")
            buildingNameToData.vals[upgradeBuildingIndex].add(["show_tech_unlock_if","{ always = no }"])
            
            computeNewCosts_Part1(buildingData, upgradeData, args, varsToValue)
            # #compute build times
            # computeNewCosts(buildingData, upgradeData, "base_buildtime", args.time_discount,varsToValue)
            
            # #compute costs
            # costsA=buildingData.splitToListIfString("cost")
            # costsB=upgradeData.splitToListIfString("cost")
            # allCostNames=list(set(costsA.names)|set(costsB.names)) #create a list that includes any cost name from either building exactly once
            # for name in allCostNames:
              # computeNewCosts(costsA, costsB, name, args.cost_discount,varsToValue)
              
              
            if "upgrades" in upgradeData.names:
              buildingDataList.append(upgradeData) #make sure we finish one branch of a tree before we start a new branch!
              
        
            
            #ICON AND LOCALIZATION:
            nameExtra="_direct_build"
            nameStringExtra=""
            if args.create_tier5_enhanced and buildingData.buildingName.replace("_direct_build","")[-3:]=="_rw":
              nameExtra+="_rw"
              nameStringExtra=" Enhanced"
              if not "icon" in buildingNameToData.vals[upgradeBuildingIndex+1].names: #if icon was already a link in the original building, we can leave it
                buildingNameToData.vals[upgradeBuildingIndex+1].add(["icon",upgradeName]) #otherwise create an icon link to the original building
              locData.append(upgradeName+'_rw:0 "$'+upgradeName+'$'+nameStringExtra+'"') #localisation link. If anyone knows what the number behind the colon means, please PN me (@Gratak in Paradox forum)
              locData.append(upgradeName+'_rw_desc:0 "$'+upgradeName+'_desc$"') #localisation link
              
            if not "icon" in buildingNameToData.vals[upgradeBuildingIndex].names: #if icon was already a link in the original building, we can leave it
              buildingNameToData.vals[upgradeBuildingIndex].add(["icon",upgradeName]) #otherwise create an icon link to the original building
            locData.append(upgradeName+nameExtra+':0 "$'+upgradeName+'$'+nameStringExtra+'"') #localisation link. If anyone knows what the number behind the colon means, please PN me (@Gratak in Paradox forum)
            locData.append(upgradeName+nameExtra+'_desc:0 "$'+upgradeName+'_desc$"') #localisation link
              
            #MAKE UNIQUE VIA INTRODUCING A FAKE MAX TIER BUILDING
            if not "upgrades" in upgradeData.names and "planet_unique" in upgradeData.names and upgradeData.get("planet_unique")=="yes": #Max tier unique
              fakeBuilding=Building(baseBuildingData.lineStart, baseBuildingData.buildingName+"_hidden_tree_root")
              fakeBuilding.lineEnd=baseBuildingData.lineEnd
              fakeBuilding.add2("potential", "{ always=no }")
              fakeBuilding.add2("planet_unique", "yes")
              fakeBuilding.add2("icon",baseBuildingData.buildingName)
              locData.append(fakeBuilding.buildingName+':0 "$'+baseBuildingData.buildingName+'$"')
              locData.append(fakeBuilding.buildingName+'_desc:0 "$'+baseBuildingData.buildingName+'_desc$"')
              upgradeData.getOrCreate("upgrades").add2(fakeBuilding.buildingName,"")
              origUpgradeData.getOrCreate("upgrades").add2(fakeBuilding.buildingName,"")
              fakeIndex=buildingNameToData.names.index(baseBuildingData.buildingName)
              buildingNameToData.insert([fakeBuilding.buildingName,fakeBuilding],fakeIndex) #insert the fake before 'baseBuilding'. upgradeBuildingIndex is now shifted but shouldn't be used anymore
              #create a scripted_trigger that checks if ANY building of this building tree/line exists
              # newList=NamesToValue(1)
              # newList.getOrCreate("OR").add2("has_building",baseBuildingData.buildingName)
              # for trigger in triggers.names[triggerIndexAtStart:]:
                # newList.get("OR").add2(trigger,"yes")
              # triggers.add2("has_"+upgradeName+"_or_lower", newList)
              
              #set this previously created scripted_trigger for unique buildings in the line, starting from top tier. Stops if there is any non-unique building (as this would become useless at that point anyway)
              # b=upgradeData
              # while 1:
                # if not "planet_unique" in b.names or b.get("planet_unique")=="no":
                  # break
                # b.getOrCreate("potential").add2("has_"+upgradeName+"_or_lower", "no")      #make unique
                # if b.lowerTier==0:
                  # break
                # else:
                  # b=b.lowerTier
              #FINISH MAKE UNIQUE
            
          if isinstance(buildingData.splitToListIfString("potential").vals[-1], NamesToValue) and len(buildingData.get("potential").vals[-1].names)==0:
            buildingData.get("potential").removeIndex(-1)   #remove potentially empty entry thanks to empire_unique buildings that cannot be copied.
          newRequirements.increaseLevelRec() #push them to correct level. list will always exist, might be empty if unused.
            

    for building in buildingNameToData.vals:
      if "is_listed" in building.names and building.get("is_listed")=="no" and "ai_allow" in building.names:
        building.replace("ai_allow", "{ always = yes }")
        
    #buildingNameToData.printAll()
        
    if args.replacement_file!='':
      equalConditions=[]
      inConditions=[]
      allConditions=[] #allConditions[i][j] will be an array consisting of: negation bool, condition type, keyword 1, keyword 2, 
      replaceClasses=[]
      searchingForReplaceKeyword=0
      activeReplace=0
      with open(args.replacement_file, 'r') as replacement_file:
        for line in replacement_file:
          if line[:2]=="IF":
            searchingForReplaceKeyword=1
            activeReplace=0
            allConditions.append([])
            conditions=line[2:].split("and")
            for condition in conditions:
              allConditions[-1].append([])
              if condition.split()[0]=="not":
                allConditions[-1][-1].append(True)
                condition=" ".join(condition.split()[1:])
              else:
                allConditions[-1][-1].append(False)
              if len(condition.strip().split("=="))==2: #len(condition.strip().split(" "))==1 and 
                allConditions[-1][-1].append("==")
                # allConditions[-1][-1].append(e.strip() for e in condition.strip().split("=="))
              elif len(condition.strip().split(" in "))==2:
                allConditions[-1][-1].append(" in ")
                # allConditions[-1][-1].append(e.strip() for e in condition.strip().split(" in "))
              else:
                print("Invalid condition in replacement file! Exiting!")
                print(line)
                print(condition.strip().split("in"))
                sys.exit(1)
              for e in condition.strip().split(allConditions[-1][-1][-1]):
                allConditions[-1][-1].append(e.strip())
          elif line[:4]=="EVAL":
            searchingForReplaceKeyword=1
            activeReplace=0
            allConditions.append([[line[:4],line[4:].strip()]])
          elif searchingForReplaceKeyword and len(line.strip())>0 and line.strip()[0]!='#':
            replaceClasses.append(NamesToValue(1))
            replaceClasses[-1].addString(line)
            replaceClasses[-1].vals[0]+="\n"
            searchingForReplaceKeyword=0
            activeReplace=1
          elif activeReplace:
            replaceClasses[-1].vals[0]+=line
      for building in buildingNameToData.vals:
        for i in range(len(replaceClasses)):
          replace=1
          for condition in allConditions[i]:
            # print(condition)
            if condition[0]=="EVAL":
              #print(condition[1])
              if eval(condition[1]):
                replace=1
              else:
                replace=0
            elif condition[1]=="==":
              if condition[0]:  #negated
                if (condition[2] in building.names) and (building.get(condition[2])==equalCondition[3]):
                  replace=0
              else:
                if (not condition[2] in building.names) or (building.get(condition[2])!=condition[3]):
                  # print(building.buildingName+" failed "+" ".join(condition[1:]))
                  replace=0
            elif condition[1]==" in ":
              if condition[3]=="buildingName":
                if (condition[0]) != (building.buildingName.find(condition[2])==-1):
                  # print(building.buildingName+" failed buildingName "+" ".join(condition[1:]))
                  replace=0
              else:
                if (condition[0]) != (not condition[2] in building.get(condition[3])):
                  # print(building.buildingName+" failed "+" ".join(condition[1:]))
                  replace=0
          if replace:
            if replaceClasses[i].names[0] in building.names:
              #print(building.buildingName)
              #replaceClasses[i].printAll()
              building.replace(replaceClasses[i].names[0], replaceClasses[i].vals[0])
     
    
    buildingNameToData.removeDuplicatesRec()
      
    #OUTPUT
    if not args.create_standalone_mod_from_mod: #done elsewhere by mostly copying their mod file in this case
      modfileName=os.path.dirname(args.output_folder)
      if modfileName=='' or modfileName==".": #should only happen if args.output_folder is a pure foldername in which case 'os.path.dirname' is unessecary anyway
        modfileName=args.output_folder
      with open(modfileName+".mod",'w') as modfile:
        modfile.write(scriptDescription)
        prio=""
        if args.load_order_priority:
          prio="!"
        if args.custom_mod_name:
          modName=args.custom_mod_name
        else:
          modName=modfileName
        modfile.write('name="{}{}"\n'.format(prio,modName))
        modfile.write('path="mod/{}"\n'.format(args.output_folder.rstrip(os.sep)))
        modfile.write('tags={\n')
        for tag in args.tags.split(","):
          modfile.write('\t"'+tag+'"\n')
        modfile.write('}\n')
        modfile.write('supported_version="{}"\n'.format(args.gameVersion))
        if args.picture_file:
          modfile.write('picture="{}"'.format(args.picture_file))
    with open(buildingFileName,'r') as inputFile:
      if args.join_files:
        outfileBaseName="JOINED"+os.path.basename(inputFile.name)+".txt"
      else:
        outfileBaseName=os.path.basename(inputFile.name)
      if not args.just_copy_and_check:
        #LOCALISATION OUTPUT
        if not os.path.exists(args.output_folder+"/localisation"):
          os.mkdir(args.output_folder+"/localisation")
        for language in args.languages.split(","):
          if not os.path.exists(args.output_folder+"/localisation/"+language):
            os.mkdir(args.output_folder+"/localisation/"+language)
          with codecs.open(args.output_folder+"/localisation/{}/build_upgraded_{}_l_{}.yml".format(language,outfileBaseName.replace(".txt",""),language),'w', "utf-8") as locOutPutFile:
            locOutPutFile.write(u'\ufeff')
            locOutPutFile.write("l_"+language+":"+"\n")
            locOutPutFile.write(scriptDescription)
            for line in locData:
              locOutPutFile.write(" "+line+"\n")
        
        #scripted_triggers OUTPUT
        triggerFile=open(args.output_folder+"/common/scripted_triggers/build_upgraded_"+outfileBaseName.replace(".txt","")+"_triggers.txt",'w')
        triggerFile.write(scriptDescription)
        triggers.writeAll(triggerFile)
      
      #BUILDING OUTPUT
      if len(copiedBuildings)>0:
        for b in buildingNameToData.vals:
          b.replaceAllHasBuildings(copiedBuildings)
      
      if args.create_standalone_mod_from_mod and args.just_copy_and_check:
        outputFileName=outPath+outfileBaseName
      else:
        outputFileName=outPath+"build_upgraded_"+outfileBaseName
      with open(outputFileName,'w') as outputFile:
        outputFile.write(scriptDescription)
        lineIndex=0
        curBuilding=0
        if args.join_files:
          varsToValue.writeAll(outputFile)
          outputFile.write("\n")
          buildingNameToData.writeAll(outputFile)
        else:
          for line in inputFile:          
            lineIndex+=1
            if curBuilding>=len(buildingNameToData.vals) or lineIndex<buildingNameToData.vals[curBuilding].lineStart:
              outputFile.write(line)
            while curBuilding<len(buildingNameToData.vals) and lineIndex==buildingNameToData.vals[curBuilding].lineEnd:
              outputFile.write(buildingNameToData.names[curBuilding]+" = {\n")
              buildingNameToData.vals[curBuilding].writeAll(outputFile)
              outputFile.write("}\n")
              curBuilding+=1
  if not args.just_copy_and_check:
    copiedBuildingsFile.close()
    with open(copiedBuildingsFileName) as file:
      newCopiedBuilings=[line.strip() for line in file]
    if newCopiedBuilings!=copiedBuildings and not args.just_copy_and_check and allowRestart:
      main(copy.deepcopy(args),0)
  
  
def killWindowsBackSlashesWithFire(string):
  return os.path.normpath(string).replace(os.sep,"/")
  
if __name__ == "__main__":
  argv=sys.argv[1:]
  args=parse(argv)
  
  args.output_folder=os.path.normpath(args.output_folder.strip('"'))
  if args.output_folder[0]==".":
    args.output_folder=args.output_folder[1:].lstrip(os.sep)
  args.output_folder+="/"
  
  if not os.path.exists(args.output_folder):
    os.mkdir(args.output_folder)
  if args.create_standalone_mod_from_mod:
    rerunName=os.path.split(os.path.dirname(args.output_folder))[-1]+"_rerun.py" #foldername, not path!
  elif args.just_copy_and_check:
   rerunName=args.output_folder+"/rerun_just_copy_and_check.py"
  else:
    rerunName=args.output_folder+"/rerun.py" 
  with open(rerunName, 'w') as file:
    file.write("#!/usr/bin/env python3\n")
    file.write("# -*- coding: utf-8 -*-\n")
    file.write("import subprocess\n")
    file.write("import os\n")
    file.write("os.chdir(os.path.dirname(os.path.abspath(__file__)))\n")
    if not args.create_standalone_mod_from_mod:
      file.write("os.chdir('..')\n")
    callString=os.path.normpath("subprocess.call('python ./createUpgradedBuildings.py "+'"'+'" "'.join(argv)+'"'+"', shell=True)\n").replace(os.sep,"/")
    file.write(callString)
  if args.create_standalone_mod_from_mod:
    modFileName=args.buildingFileNames[0]
    # print(modFileName)
    with open(modFileName) as modFile:
      modFileCont=[line for line in modFile]
      pathString='path="mod/'+killWindowsBackSlashesWithFire(args.output_folder.lstrip("."))+'"\n'
    for i in range(len(modFileCont)):
      if modFileCont[i][:5].strip()=="path=":
        path=os.path.normpath(modFileCont[i][5:].strip().strip('"')).replace(os.sep,"/")      
        modFileCont[i]=pathString
      if modFileCont[i][:8].strip()=="archive=":
        path=os.path.normpath(modFileCont[i][8:].strip().strip('"')).replace(os.sep,"/")
        import zipfile
        zip_ref = zipfile.ZipFile(path, 'r')
        path=path.replace(".zip","/")
        zip_ref.extractall(path)
        zip_ref.close()
        modFileCont[i]=pathString
      if modFileCont[i][:5].strip()=="name=":
        if args.custom_mod_name:
          modFileCont[i]='name="'+args.custom_mod_name+'"\n'
        else:
          modFileCont[i]=modFileCont[i].strip()[:-1] #remove quote and newline
          modFileCont[i]+='_direct_build"\n'
    if path[:3]=="mod":
      path=path[4:]#hopefully taking away mod and slash, backslash
    path=path.strip()
    # if args.custom_mod_name:
      # newModFileName=args.custom_mod_name+".mod"
    # else:
      # newModFileName=modFileName.replace(".mod","_direct_build.mod")
    newModFileName=os.path.split(os.path.dirname(args.output_folder))[-1]+".mod" #foldername, not path!
    with open(newModFileName,'w') as modFile:
      for line in modFileCont:
        modFile.write(line)
        
    buildingArgs=copy.deepcopy(args)
    buildingArgs.buildingFileNames=[path+"/common/buildings/*"]
    main(buildingArgs,0)
        
    otherFilesArgs=copy.deepcopy(args)
    otherFilesArgs.buildingFileNames=[]    
    otherFilesArgs.just_copy_and_check=True
    otherFilesArgs.join_files=False
    # otherFilesArgs.replacement_file=''
    for root, dirs, files in os.walk(path):
      # if len(files)>0:
      rootWithoutPath=root.rstrip(".").replace(path,"",1)
      if not os.path.exists(args.output_folder+rootWithoutPath):
        os.mkdir(args.output_folder+rootWithoutPath)
      if not root[-16:]=="common"+os.sep+"buildings":
        for file in files:
          if file[-4:]==".txt" and rootWithoutPath!="":
            # print(rootWithoutPath)
            # sys.exit(0)
            otherFilesArgs.output_folder=args.output_folder+rootWithoutPath+"/"
            otherFilesArgs.buildingFileNames=[root+"/"+file]
            main(otherFilesArgs,0)
          else:
            # print(root)
            # print(file)
            copyfile(root+"/"+file, args.output_folder+"/"+rootWithoutPath+"/"+file)
    # print(otherFilesArgs.buildingFileNames)   
    # sys.exit(0)
    #otherFilesArgs.buildingFileNames=path+"/common/scripted_triggers/*"

    
    main(buildingArgs,0)
  else:
    main(args)