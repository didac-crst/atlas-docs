(() => {
  const relationship = document.getElementById("relationship");
  const target = document.getElementById("target");
  const dataNode = document.getElementById("concepts-data");
  if (!relationship || !target || !dataNode) return;

  let conceptsByOntology = {};
  try {
    conceptsByOntology = JSON.parse(dataNode.textContent || "{}");
  } catch (_) {
    conceptsByOntology = {};
  }

  function fillTargets() {
    const selected = relationship.options[relationship.selectedIndex];
    const ontology = selected ? selected.dataset.ontology || "*" : "*";
    const concepts = conceptsByOntology[ontology] || conceptsByOntology["*"] || [];
    target.innerHTML = "";
    for (const concept of concepts) {
      const option = document.createElement("option");
      option.value = concept.code;
      option.textContent = concept.name;
      target.appendChild(option);
    }
  }

  relationship.addEventListener("change", fillTargets);
  fillTargets();
})();
