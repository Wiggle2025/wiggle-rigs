// ===============================
// Rig dataset
// ===============================

const rigs = [

{
id: "running_sinker",
name: "Running Sinker Rig",
url: "https://wiggleyawormrigs.com/online-shop/ols/products/4-x-complete-20lb-brim-bream-running-sinker-rigs-size10-hook-15gm-sinker",
environment: ["Surf","Estuary"],
species: ["Whiting","Bream","Flathead","Mixed"],
bait: ["Worm","Pilchard","Strip bait"],
structure: ["Clean sand"],
sweep: ["None"],
distance: ["Short"],
sinker: "Ball sinker",
why: "Simple presentation ideal for natural bait movement in calm conditions."
},

{
id: "whiting_paternoster",
name: "Whiting Double Paternoster Rig",
url: "https://wiggleyawormrigs.com/online-shop/ols/products/3x-hand-tied-whiting-double-paternoster-rigs-2-worm-hooks--blue-fisheye-beads",
environment: ["Surf","Estuary"],
species: ["Whiting"],
bait: ["Worm"],
structure: ["Clean sand"],
sweep: ["None","Moderate"],
distance: ["Short"],
sinker: "Ball sinker",
why: "Keeps worm baits elevated above sand and away from pickers."
},

{
id: "sliding_snell_40",
name: "40lb Sliding Snell Estuary Snapper & Mulloway Rig",
url: "https://wiggleyawormrigs.com/online-shop/ols/products/4x-40lb-sliding-snelled-hook-rigs-2x-circle-3-slash-0-hooks-and-lumo-beads-4x-40l-sld-snl1",
environment: ["Estuary"],
species: ["Snapper","Mulloway"],
bait: ["Pilchard","Strip bait"],
structure: ["Clean sand","Light reef"],
sweep: ["None","Moderate"],
distance: ["Short","Medium"],
sinker: "Ball sinker",
why: "Twin snelled hooks improve hook-up rates while maintaining subtle presentation."
},

{
id: "sliding_snell_60",
name: "60lb Sliding Snell Snapper & Mulloway Rig",
url: "https://wiggleyawormrigs.com/online-shop/ols/products/4x-60lb-sliding-snelled-double-hook-rig-2x-5-slash-0-octopus-circle-hooks-with-luminous-beads",
environment: ["Surf"],
species: ["Snapper","Mulloway"],
bait: ["Pilchard","Strip bait","Slab bait"],
structure: ["Clean sand"],
sweep: ["Moderate"],
distance: ["Medium","Long"],
sinker: "Star sinker",
why: "Heavier leader handles surf pressure while twin hooks secure large predators."
},

{
id: "flathead_fishfinder",
name: "Flathead Fish Finder Rig",
url: "https://wiggleyawormrigs.com/online-shop/ols/products/4x-40lb-mono-flathead-fish-finder-rigs2-x-10-hookssliding-weight-clip-beads",
environment: ["Surf","Estuary"],
species: ["Flathead"],
bait: ["Pilchard","Strip bait","Live bait"],
structure: ["Clean sand"],
sweep: ["None","Moderate"],
distance: ["Short","Medium"],
sinker: "Ball sinker",
why: "Sliding sinker lets flathead mouth bait naturally before feeling resistance."
}

];


// ===============================
// Optional rig guide links
// ===============================

const rigGuides = {

running_sinker:
"/rig-setup-guides/running-sinker-rig",

whiting_paternoster:
"/rig-setup-guides/paternoster-rig",

sliding_snell_40:
"/rig-setup-guides/sliding-snell-rig",

sliding_snell_60:
"/rig-setup-guides/sliding-snell-rig",

flathead_fishfinder:
"/rig-setup-guides/fish-finder-rig"

};


// ===============================
// Main selection function
// ===============================

function findRig() {

const selectedEnvironment =
document.getElementById("environment").value;

const selectedSpecies =
document.getElementById("species").value;

const selectedBait =
document.getElementById("bait").value;

const selectedStructure =
document.getElementById("structure").value;

const selectedSweep =
document.getElementById("sweep").value;

const selectedDistance =
document.getElementById("distance").value;


let bestRig = null;
let bestScore = -1;
let alternativeRig = null;
let altScore = -1;


// ===============================
// scoring loop
// ===============================

rigs.forEach(rig => {

let score = 0;


if (rig.environment.includes(selectedEnvironment))
score += 3;

if (rig.species.includes(selectedSpecies))
score += 3;

if (rig.bait.includes(selectedBait))
score += 2;

if (rig.structure.includes(selectedStructure))
score += 2;

if (rig.sweep.includes(selectedSweep))
score += 2;

if (rig.distance.includes(selectedDistance))
score += 2;


// species name bonus weighting

if (
rig.name.toLowerCase()
.includes(selectedSpecies.toLowerCase())
)
score += 2;


// assign best + alternative rigs safely

if (score > bestScore) {

altScore = bestScore;
alternativeRig = bestRig;

bestScore = score;
bestRig = { ...rig };

}
else if (score > altScore) {

altScore = score;
alternativeRig = { ...rig };

}

});


// ===============================
// render result
// ===============================

const resultLink =
document.getElementById("resultLink");

resultLink.textContent = bestRig.name;

resultLink.setAttribute("href", bestRig.url);


document.getElementById("whyText")
.textContent = bestRig.why;

document.getElementById("sinkerText")
.textContent = bestRig.sinker;


// confidence level logic

let confidence = "Multiple rigs suitable";

if (bestScore >= 10)
confidence = "Strong match";

document.getElementById("confidenceText")
.textContent = confidence;


// ===============================
// alternative rig link
// ===============================

const altContainer =
document.getElementById("altText");

if (alternativeRig) {

altContainer.innerHTML =
'<a href="' +
alternativeRig.url +
'">' +
alternativeRig.name +
'</a>';

}


// ===============================
// optional rig guide link
// ===============================

const guideLink =
document.getElementById("guideLink");

if (rigGuides[bestRig.id]) {

guideLink.setAttribute(
"href",
rigGuides[bestRig.id]
);

guideLink.style.display = "inline";

}

}
