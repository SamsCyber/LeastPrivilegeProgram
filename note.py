#!/usr/bin/env python3
import os
import sys
from base64 import b64encode
import getopt
import re
import pipes

# directory to be created by the process that will have permissions only the child subprocess can access
NOTE_DIR = "./noticeboard/"

# function for creating/saving a new note
def write(subject: str, noteContent:str) -> str:
    
    # variables for not relevent info, identifier will be the 4 digit code, filename is the subject appended with _
    identifier = str("")
    filename = str(subject + "_")
    unique = False
    # check if directory exists, if not, create and set permissions
    if not(os.path.exists(NOTE_DIR)):
        os.mkdir(NOTE_DIR)
    os.chown(NOTE_DIR, 0, 0)
    os.chmod(NOTE_DIR, 0o700)
        
    
    # while loop to keep generating identifiers until it is confirmed as unique
    while(not(unique)):
        identifier = ""
        i = 0
        while(i<4):
            # use truly random urandom to generate random bytes
            random_byte = os.urandom(1)
            token = b64encode(random_byte).decode('utf-8')[:1]
            # only accept upper case letters
            if(token.isalpha() and token.isupper()):
                identifier = identifier + token
                i = i+1
        currentfiles = [f for f in os.listdir(NOTE_DIR) if os.path.isfile(os.path.join(NOTE_DIR, f))]
        # filters through a list of files in directory to make sure identifier doesn't exist already
        if currentfiles:
            for i in currentfiles:
                if(i[-4:] == identifier):
                    unique = False
                    break
                else:
                    unique = True
        else:
            unique = True
                
    filename = filename + identifier
    location = NOTE_DIR+filename
    # if identifier unique, write note with its content
    try:
        with open(location, "w") as note:
            note.write(noteContent)
        os.chown(location, 0, 0)
        os.chmod(location, 0o700)
    except IOError as e:
        raise IOError("failure to create note")
    return identifier

# function for returning all the notes, that pattern match with a substring, content
def read(substring: str) -> list:

    toRead = []
    currentfiles = [f for f in os.listdir(NOTE_DIR) if os.path.isfile(os.path.join(NOTE_DIR, f))]
    # search through the subjects of every file and search for substring in the name
    for i in currentfiles:
        if substring in i[:-5]:
            toRead.append(i)
    contents = []
    # return all the notes that contain the substring in their subject
    for i in toRead:
        with open(NOTE_DIR+i, "r") as note:
            contents.append(note.read())
    return contents
        
# remove function to delete the note with the given identifier
def rem(identifier: str) -> str:
    
    removed = False
    fileRemoved = ""
    currentfiles = [f for f in os.listdir(NOTE_DIR) if os.path.isfile(os.path.join(NOTE_DIR, f))]
    # filters through the files looking only at the identifier and matches exactly to the passed in identifier, if found, delete the note
    for i in currentfiles:
        if (identifier == i[-4:]):
            os.remove(NOTE_DIR+i)
            fileRemoved=i
            removed = True
            break
    
    # if not found, return such
    if removed == False:
        return("NoFileFound")
    return ("FileRemoved " + fileRemoved)

# this method handles all the dirty business of the parent process
def parentCommandCentre(pid: int, pipetuple: tuple):
    
    if pid > 0:
        command = sys.argv[1] 
        file = sys.argv[2]
        # filters what command is passed in, strict equality checks mean that no unexpected input can be passed in or bugs created
        if(command == "write" or command == "read"):
            # stricter checks for specific args
            if not re.match("^[a-zA-Z]*$", file):
                print("Error, the filename must only consist of alphabetical characters.")
                return 0
            elif(len(file) > 30):
                print("Error, the filename must consist of less than 30 characters")
            # if write arg is called, collect the note content
            elif(command=="write"):
                noteContent = input("")
                if(len(noteContent)>100 or len(noteContent)<= 0):
                    print("note has a maximum limit of 100 characters and a minimum of at least one character")
                    return 0
                try:
                    # pass the arguments if satisfactory to the higher privileged child process
                    constructString = command +":"+file+":"+noteContent
                    os.write(pipetuple[0], constructString.encode())
                    os.close(pipetuple[0])
                    # read back the result of the child process running the commands with elevated privileges
                    r = os.fdopen(pipetuple[1])
                    readIn = r.read()
                    os.close(pipetuple[1])
                    if(readIn != "ERROR"):
                        print("Your note is " + readIn)
                except os.error as e:
                    print("There was an error communicating between pipes" + str(e))
            # if requested function is 'read'
            elif(command=="read"):
                try:
                    # again pass the required arguments down the pipe to child
                    constructString = command +":"+file+":"
                    os.write(pipetuple[0], constructString.encode())
                    os.close(pipetuple[0])
                    r = os.fdopen(pipetuple[1])
                    # read back child response
                    readIn = r.read()
                    os.close(pipetuple[1])
                    print(readIn)
                except os.error as e:
                    print("There was an error communicating between pipes" + e)
        # similar situation as two previous functions but for the remove function
        if(command == "remove"):
            if(len(file) > 4):
                print("Input is too long for an identifier")
            else:
                try:
                    constructString = command +":"+file+":"
                    os.write(pipetuple[0], constructString.encode())
                    os.close(pipetuple[0])
                    r = os.fdopen(pipetuple[1])
                    readIn = r.read()
                    os.close(pipetuple[1])
                    print(readIn)
                except os.error as e:
                    print("There was an error communicating between pipes" + e)
    
# This method handles all the function calls that the child process will be carrying out for the parent process because of its elevated privileges
def childCommandCentre(pid: int, pipetuple: tuple):
    
    if pid == 0:
        try:
            os.seteuid(0)
        except PermissionError as e:
            error = "ERROR: " + str(e)
            print(error + ". You must run the program as root")
        try:
            # first read in whatever is passed from the parent process, as this is how the process decides what action to take next
            c1 = os.fdopen(pipetuple[1])
            receivedString = c1.read()
            inputs = receivedString.split(":", 2)
            os.close(pipetuple[1])
        except os.error as e:
            print("There was an error communicating between pipes" + e)
        # block for writing
        if(inputs[0] == "write"):
            try:
                # carry out the write and then remove its own privilege as it no longer needs it for this run of the script
                identifier = write(inputs[1], inputs[2])
                os.write(pipetuple[0], identifier.encode())
                os.close(pipetuple[0])
            except(IOError) as e:
                error = "ERROR: " + str(e)
                os.write(pipetuple[0], error.encode())
                os.close(pipetuple[0])
        # block for reading
        if(inputs[0] == "read"):
            try:
                listOfNotes = read(inputs[1])
                toSend = "\n".join(listOfNotes)
                os.write(pipetuple[0], toSend.encode())
                os.close(pipetuple[0])
            except(Exception) as e:
                error = "ERROR: " + str(e)
                os.write(pipetuple[0], error.encode())
                os.close(pipetuple[0])
        # block for removing notes
        if(inputs[0] == "remove"):
            try:
                print(inputs[1])
                result = rem(inputs[1])
                # if the remove was successful, construct a string for the parent process to present to its user containing the filename.
                if(result.startswith("FileRemoved")):
                    toSend = "removed "+result[12:]
                    os.write(pipetuple[0], toSend.encode())
                    os.close(pipetuple[0])
                else:
                    os.write(pipetuple[0], "No file was found to remove".encode())
                    os.close(pipetuple[0])
            except(Exception) as e:
                error = "ERROR: " + str(e)
                print(type(e))
                os.write(pipetuple[0], error.encode())
                os.close(pipetuple[0])
                
               

def main() -> int:
    # initialise two pipes, such that we can simulate a bidirectional pipe system
    r0,w0 = os.pipe()
    r1,w1 = os.pipe()
    
    # fork the process into child and parent
    pid = os.fork()
    
    # if process id is greater than 0 this is the parent process
    if pid > 0:
        try:
            # remove permissions of the parent process, so it has to rely on the separated root process
            os.setuid(10000)
        except PermissionError as e:
            print("You do not have permission to run this file, please run this file as root")
            sys.exit()
        os.close(r1)
        os.close(w0)
        parentCommandCentre(pid, (w1, r0))
    
    # if process id is 0 this is the child process
    elif pid == 0:
        os.close(w1)
        os.close(r0)
        childCommandCentre(pid, (w0, r1))
            
            
if __name__ == "__main__":
    if(len(sys.argv) != 3):
        print(" please input two arguments: <method> <target> \n")
    else:
        main()
    