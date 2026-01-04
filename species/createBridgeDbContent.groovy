import groovy.json.JsonSlurper

def fileContent = new File("species_ncbi.json").text 

def jsonSlurper = new JsonSlurper()
def object = jsonSlurper.parseText(fileContent)

def organismData = new File("organisms.tsv").readLines()*.split('\t')
organismCodes = new HashSet<String>();
organismData.each { organism ->
  code = organism[3]
  if (organismCodes.contains(code)) {
    println "Duplicate found! -> " + code
  } else {
    organismCodes.add(code)
  }
}

def String uniqueCode(String speciesName) {
  firstSpaceIndex = searchName.indexOf(" ")
  colOne = searchName.substring(0, firstSpaceIndex)
  colTwo = searchName.substring(firstSpaceIndex).trim()
  newCode = "" + colOne.charAt(0) + colTwo.charAt(0)
  if (organismCodes.contains(newCode)) {
    newCode = "" + colOne.charAt(0) + colTwo.charAt(0) + colTwo.charAt(1)
    if (organismCodes.contains(newCode)) {
      newCode = "" + colOne.charAt(0) + colOne.charAt(1) + colTwo.charAt(0)
      if (organismCodes.contains(newCode)) {
        return "Xxx"
      } else {
        organismCodes.add(newCode)
        return newCode
      }
    } else {
      organismCodes.add(newCode)
      return newCode
    }
  } else {
    organismCodes.add(newCode)
    return newCode
  }
}

object.each { search ->
  searchName = search.name.trim()
  if ("Exact" == search.matchType) {
    bestResult = search.bestResult
    matchName = bestResult.matchedCanonicalFull
    if (searchName = matchName) {
      if (searchName.contains(" ")) {
        firstSpaceIndex = searchName.indexOf(" ")
        colOne = searchName.substring(0, firstSpaceIndex)
        colTwo = searchName.substring(firstSpaceIndex).trim()
        ncbi = bestResult.recordId
        code = uniqueCode(searchName)
        println "$colOne\t$colTwo\t\t$code\t$ncbi"
      } else {}
    }
  }
}
