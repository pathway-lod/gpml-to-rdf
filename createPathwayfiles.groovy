import java.util.ArrayList
import java.util.List
import java.util.Map
import java.util.HashMap

import java.nio.file.Path
import java.nio.file.Files

import static groovy.io.FileType.FILES

Map<String,List> failedTests = new HashMap<>();

def dir = new File("orig");
def files = [];
dir.traverse(type: FILES, maxDepth: 0) {
  if (it.name.endsWith(".gpml")) {
    files.add(it)
  }
};

counter = 0
files.each { file ->
  counter = counter + 1
  wpid = "PC" + counter
  println file.name + " -> ${wpid}"
  source = new File(file.path)
  target = new File("orig-renamed/${wpid}.gpml")
  Files.copy(source.toPath(), target.toPath())
}
