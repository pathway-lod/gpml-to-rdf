import groovy.json.JsonSlurper

def fileContent = new File("species_ncbi.json").text 

def jsonSlurper = new JsonSlurper()
def object = jsonSlurper.parseText(fileContent)

def organismData = new File("organisms.tsv").readLines()*.split('\t')
organismCodes = new HashSet<String>();
commonNames = new HashMap<String,String>();
organismData.each { organism ->
  code = organism[3]
  commonName = organism[2]
  if (organismCodes.contains(code)) {
    println "Duplicate found! -> " + code
  } else {
    organismCodes.add(code)
  }
  if ("" != commonName) {
    println "Added $code -> $commonName"
    commonNames.put(code, commonName)
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
        // println "$colOne\t$colTwo\t\t$code\t$ncbi"
        // println "\t\tothers.put(\"$searchName\",\"$ncbi\");"
        javaName = colOne + colTwo.substring(0,1).toUpperCase() + colTwo.substring(1)
        optionalCommonName = (commonNames.containsKey(code)) ? "\"" + commonNames.get(code) +"\", " : "";
        println "\t$javaName(\"$searchName\",\"$code\",$optionalCommonName$ncbi);"
      } else {}
    }
  }
}
