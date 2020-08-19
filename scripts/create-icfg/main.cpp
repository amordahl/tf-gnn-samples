#include <vector>
#include <queue>
#include <cxxabi.h>
#include <iostream>
#include <llvm/IR/AbstractCallSite.h>
#include <llvm/IR/Constants.h>
#include <llvm/IR/DebugLoc.h>
#include <llvm/IR/Function.h>
#include <llvm/IR/Instruction.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/IntrinsicInst.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IR/CFG.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/SMLoc.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/raw_ostream.h>
#include <llvm/Support/ManagedStatic.h>
#include <algorithm>
#include <memory>
#include <string>

std::string cxx_demangle(const std::string &mangled_name) {
  int status = 0;
  char *demangled =
      abi::__cxa_demangle(mangled_name.c_str(), NULL, NULL, &status);
  std::string result((status == 0 && demangled != NULL) ? demangled
                                                        : mangled_name);
  free(demangled);
  return result;
}

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cout << "usage: <prog> <IR file>\n";
    return 1;
  }
  // parse an IR file into an LLVM module
  llvm::SMDiagnostic Diag;
  std::unique_ptr<llvm::LLVMContext> C(new llvm::LLVMContext);
  std::unique_ptr<llvm::Module> M = llvm::parseIRFile(argv[1], Diag, *C);
  // check if the module is alright
  bool broken_debug_info = false;
  if (llvm::verifyModule(*M, &llvm::errs(), &broken_debug_info)) {
    llvm::errs() << "error: module not valid\n";
    return 1;
  }
  if (broken_debug_info) {
    llvm::errs() << "caution: debug info is broken\n";
  }
  auto F = M->getFunction("main");
  if (!F) {
    llvm::errs() << "error: could not find function 'main'\n";
    return 1;
  }
  // set up basic block list
  std::vector<llvm::BasicBlock*> basicBlockRecords;

  // set up queues
  std::queue<llvm::BasicBlock*> basicBlocksToProcess;
  std::queue<std::string> fs;

  // initially add main to fs
  fs.push("main");

  while (fs.size() > 0) {
    std::string name = fs.front();
    fs.pop();
    auto F = M->getFunction(name);
    if (!F) {
      llvm::errs() << "error: could not find function '" << name << "'\n";
      continue;
    }
    llvm::outs() << "[Function: " << F->getName() << "]\n";

    // add the entry block to the queue.
    llvm::BasicBlock* begin = nullptr;
    for (auto &BB: *F) {
      if (begin == nullptr) begin = &BB;
    }
    if (!begin) {
      llvm::errs() << "error: function " << name << " is empty\n";
      continue;
    }
    basicBlocksToProcess.push(begin);

    while (basicBlocksToProcess.size() > 0) {
      llvm::BasicBlock* bb = basicBlocksToProcess.front();
      basicBlocksToProcess.pop();
      // check if basic block is already in records; if so, print id
      std::vector<llvm::BasicBlock*>::iterator itr = std::find(basicBlockRecords.begin(), basicBlockRecords.end(), bb);
      if (itr == basicBlockRecords.end()) {
	// not in queue.
	llvm::errs() << "Adding new basic block to queue: " << bb << "\n";
	basicBlockRecords.push_back(bb);
	llvm::outs() << "[BB " << bb << "]\n";
	
	// process basic block
	for (auto &I : *bb) {
	  if (auto Caller = llvm::dyn_cast<llvm::CallInst>(&I)) {
	    llvm::outs() << "[Caller: " << I << "]\n";
	    llvm::Function* f = Caller->getCalledFunction();
	    if (!f) { continue; }
	    llvm::outs() << "[Callee: " << f->getName() << "]\n";
	    fs.push(f->getName().str());
	  } else {
	    llvm::outs() << I << "\n";
	  }
	}

	// push successors onto queue.
	for (llvm::BasicBlock *succ : successors(bb)) {
	  basicBlocksToProcess.push(succ);
	  llvm::outs() << "Successor: " << succ << "\n";
	  llvm::errs() << *succ << "\n";
	}
	
      } else {
	//	int ix = std::distance(basicBlockRecords.begin(), itr);
	//	llvm::outs() << "[BB " << bb << "]\n";
	continue;
      }
    }
  
    /*  for (auto &BB : *F) {
    for (auto &I : BB) {
      // if I is a call instruction
      if (auto Caller = llvm::dyn_cast<llvm::CallInst>(&I)) {
	llvm::outs() << "caller: '" << I << "'\n";
	llvm::Function* f = Caller->getCalledFunction();
	llvm::outs() << "callee: '" << f->getName();
      } else {
	I.print(llvm::outs());
	}*/

           // TODO: Analyze instruction 'I' here.
      // (see http://llvm.org/doxygen/classllvm_1_1Instruction.html)
      // For instance, let's check if 'I' is an 'AllocaInst':
      //
      // if (auto Alloc = llvm::dyn_cast<llvm::AllocaInst>(&I)) {
      //    At this point you can use the memberfunctions of llvm::AllocaInst
      //    on the pointer variable Alloc as it is a more specialized sub-type
      //    of llvm::Instruction.
      //    llvm::outs() << "Found an alloca instruction!\n";
      // }
      //
      // For the further tasks you may like to familiarize yourself with the
      // sub-instructions 'llvm::LoadInst' and 'llvm::StoreInst' as well as
      // 'llvm::CallInst'. Use if-constructs like shown in the above.
      //
      // If you just want to figure out if a variable is an instance of a
      // certain type you can use 'llvm::isa<>()' like this:
      //
      // if (llvm::isa<llvm::CallInst>(&I)) {
      //   llvm::outs() << "Found a CallInst!\n";
      // }
      //
      // Both, 'llvm::isa' and 'llvm::dyn_cast' only work for variables within
      // the universe of LLVM. These features have been crafted for efficiency
      // and only require a single look-up; so do not be afraid to use them.
      // If you need to find inheritance relationsships in non-LLVM context use
      // C++'s classical 'dynamic_cast'.
  }
  llvm::llvm_shutdown();
  return 0;
}
