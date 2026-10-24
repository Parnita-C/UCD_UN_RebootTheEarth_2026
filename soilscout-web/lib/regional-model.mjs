export const COST_STUDY = 'https://coststudyfiles.ucdavis.edu/uploads/pub/2022/09/28/2022covercropsbenefits.pdf';
export const COMET_REPORT = 'https://comet-planner.com/api/resource/pdf/COMET-Planner_Report.pdf';
export const PAYMENT_SOURCE = 'https://www.indigoag.com/blog/announcing-indigo-carbon-payment-rate-for-the-2020-and-2021-crops';
export const VESTING_SOURCE = 'https://app.indigoag.com/programs/learn/paper/why-does-it-take-time-to-repair-soil-to-store-carbon';
export const DEFAULT_IMPLEMENTATION = 'Add Legume Seasonal Cover Crop to Intensive Till Irrigated Cropland';
export const VESTING = [.5,.2,.1,.1,.1];
const finite = x => typeof x === 'number' && Number.isFinite(x);
/** @param {{record: any, acres: number|null, payment?: number|null, buffer?: number|null, delay?: number|null, annualCost?: number|null, annualSavings?: number|null, setup?: number|null, already?: boolean, eligibleSystem?: boolean}} input */
export function regionalScenario({record, acres, payment=30, buffer=20, delay=1, annualCost=null, annualSavings=0, setup=0, already=false, eligibleSystem=true}) {
 if(!record || !eligibleSystem || !finite(acres) || acres<=0 || acres>1e6 || !finite(record.soil_carbon_co2)) return null;
 const annualSoilCO2=record.soil_carbon_co2*acres;
 const annualC=annualSoilCO2*12/44;
 const annualGHG=finite(record.total_ghg_co2)?record.total_ghg_co2*acres:null;
 const validTerms=[payment,buffer,delay,annualSavings,setup].every(finite)&&payment>=0&&payment<=10000&&buffer>=0&&buffer<=100&&Number.isInteger(delay)&&delay>=0&&delay<=20&&annualSavings>=0&&setup>=0;
 const revenueAllowed=validTerms&&!already&&record.cpsnum!==336&&annualGHG!==null;
 const annualReceipts=revenueAllowed?Math.max(0,annualGHG)*(1-buffer/100)*payment:null;
 const costKnown=finite(annualCost)&&annualCost>=0&&finite(setup)&&setup>=0;
 const rows=[1,3,5].map(year=>{
  let factor=0;
  for(let cohort=1;cohort<=year;cohort++) for(let k=0;k<VESTING.length;k++) if(cohort+delay+k<=year) factor+=VESTING[k];
  const cashReceived=annualReceipts===null?null:annualReceipts*factor;
  const cost=costKnown?annualCost*acres*year+setup:null;
  const savings=validTerms?annualSavings*acres*year:null;
  return {year,carbon:annualC*year,co2:annualSoilCO2*year,ghg:annualGHG===null?null:annualGHG*year,indicativeRevenue:annualReceipts===null?null:annualReceipts*year,cashReceived,cost,savings,net:cashReceived!==null&&cost!==null&&savings!==null?cashReceived+savings-cost:null};
 });
 return {annualC,annualSoilCO2,annualGHG,annualReceipts,rows,validTerms};
}
