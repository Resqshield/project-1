/**
 * Client-side gazetteer (X1): towns, cities and notable places mapped to their
 * district id, so free-text search ("Kochi", "Munnar", "Kovalam") resolves to
 * the right district drill-down — no geocoding API needed.
 *
 * District names themselves are added at runtime from lib/districts, so this
 * list only needs to cover sub-district places and common aliases.
 */
export interface Place {
  name: string;
  districtId: string;
  /** optional pincode for numeric lookups */
  pin?: string;
}

export const PLACES: Place[] = [
  // Thiruvananthapuram
  { name: 'Trivandrum', districtId: 'TVM', pin: '695001' },
  { name: 'Kovalam', districtId: 'TVM' },
  { name: 'Varkala', districtId: 'TVM' },
  { name: 'Neyyattinkara', districtId: 'TVM' },
  { name: 'Attingal', districtId: 'TVM' },
  { name: 'Nedumangad', districtId: 'TVM' },
  { name: 'Technopark', districtId: 'TVM' },
  // Kollam
  { name: 'Quilon', districtId: 'KLM', pin: '691001' },
  { name: 'Karunagappally', districtId: 'KLM' },
  { name: 'Punalur', districtId: 'KLM' },
  { name: 'Paravur', districtId: 'KLM' },
  { name: 'Kottarakkara', districtId: 'KLM' },
  // Pathanamthitta
  { name: 'Adoor', districtId: 'PTA' },
  { name: 'Thiruvalla', districtId: 'PTA' },
  { name: 'Ranni', districtId: 'PTA' },
  { name: 'Sabarimala', districtId: 'PTA' },
  { name: 'Konni', districtId: 'PTA' },
  // Alappuzha
  { name: 'Alleppey', districtId: 'ALP', pin: '688001' },
  { name: 'Kuttanad', districtId: 'ALP' },
  { name: 'Cherthala', districtId: 'ALP' },
  { name: 'Kayamkulam', districtId: 'ALP' },
  { name: 'Mavelikkara', districtId: 'ALP' },
  { name: 'Haripad', districtId: 'ALP' },
  // Kottayam
  { name: 'Changanassery', districtId: 'KTM' },
  { name: 'Pala', districtId: 'KTM' },
  { name: 'Vaikom', districtId: 'KTM' },
  { name: 'Ettumanoor', districtId: 'KTM' },
  { name: 'Kumarakom', districtId: 'KTM' },
  { name: 'Erattupetta', districtId: 'KTM' },
  // Idukki
  { name: 'Munnar', districtId: 'IDK' },
  { name: 'Thodupuzha', districtId: 'IDK' },
  { name: 'Thekkady', districtId: 'IDK' },
  { name: 'Kattappana', districtId: 'IDK' },
  { name: 'Cheruthoni', districtId: 'IDK' },
  { name: 'Vandiperiyar', districtId: 'IDK' },
  { name: 'Adimali', districtId: 'IDK' },
  // Ernakulam
  { name: 'Kochi', districtId: 'EKM', pin: '682001' },
  { name: 'Cochin', districtId: 'EKM' },
  { name: 'Aluva', districtId: 'EKM' },
  { name: 'Kakkanad', districtId: 'EKM' },
  { name: 'Fort Kochi', districtId: 'EKM' },
  { name: 'Muvattupuzha', districtId: 'EKM' },
  { name: 'Perumbavoor', districtId: 'EKM' },
  { name: 'Angamaly', districtId: 'EKM' },
  { name: 'Kothamangalam', districtId: 'EKM' },
  // Thrissur
  { name: 'Trichur', districtId: 'TSR', pin: '680001' },
  { name: 'Chalakudy', districtId: 'TSR' },
  { name: 'Guruvayur', districtId: 'TSR' },
  { name: 'Kodungallur', districtId: 'TSR' },
  { name: 'Irinjalakuda', districtId: 'TSR' },
  { name: 'Kunnamkulam', districtId: 'TSR' },
  // Palakkad
  { name: 'Palghat', districtId: 'PKD', pin: '678001' },
  { name: 'Ottapalam', districtId: 'PKD' },
  { name: 'Chittur', districtId: 'PKD' },
  { name: 'Mannarkkad', districtId: 'PKD' },
  { name: 'Shoranur', districtId: 'PKD' },
  { name: 'Nelliyampathy', districtId: 'PKD' },
  // Malappuram
  { name: 'Manjeri', districtId: 'MLP' },
  { name: 'Tirur', districtId: 'MLP' },
  { name: 'Ponnani', districtId: 'MLP' },
  { name: 'Perinthalmanna', districtId: 'MLP' },
  { name: 'Nilambur', districtId: 'MLP' },
  { name: 'Kottakkal', districtId: 'MLP' },
  // Kozhikode
  { name: 'Calicut', districtId: 'KKD', pin: '673001' },
  { name: 'Vadakara', districtId: 'KKD' },
  { name: 'Koyilandy', districtId: 'KKD' },
  { name: 'Feroke', districtId: 'KKD' },
  { name: 'Ramanattukara', districtId: 'KKD' },
  // Wayanad
  { name: 'Kalpetta', districtId: 'WYD' },
  { name: 'Sulthan Bathery', districtId: 'WYD' },
  { name: 'Mananthavady', districtId: 'WYD' },
  { name: 'Meppadi', districtId: 'WYD' },
  { name: 'Vythiri', districtId: 'WYD' },
  { name: 'Chooralmala', districtId: 'WYD' },
  // Kannur
  { name: 'Cannanore', districtId: 'KNR', pin: '670001' },
  { name: 'Thalassery', districtId: 'KNR' },
  { name: 'Payyanur', districtId: 'KNR' },
  { name: 'Taliparamba', districtId: 'KNR' },
  { name: 'Iritty', districtId: 'KNR' },
  { name: 'Mattannur', districtId: 'KNR' },
  // Kasaragod
  { name: 'Kanhangad', districtId: 'KSD' },
  { name: 'Kasargod', districtId: 'KSD' },
  { name: 'Nileshwaram', districtId: 'KSD' },
  { name: 'Bekal', districtId: 'KSD' },
  { name: 'Uppala', districtId: 'KSD' },
];
