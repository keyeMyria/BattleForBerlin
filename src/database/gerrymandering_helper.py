import functools

from src.database.db_handler import db_session
from src.database.db_helper import get_results
from src.database.models import MergedDistrict, Diff, MergedDistrictDiff


def get_gerrymandering_steps(bwk, party):
    districts = MergedDistrictDiff.query.all()
    diffs = Diff.query.all()
    results = get_results()['diff']

    bwk_districts = [district for district in districts if district.bwk == bwk]

    # Yay for local functions!
    # Sort bwk districts by their results
    def district_comparator(d1, d2):
        d1_party_result = d1.get_result_dict()[party]
        d2_party_result = d2.get_result_dict()[party]
        sorted_d1_tuples = sorted(d1.get_result_dict().items(), key=lambda d: d[1], reverse=True)
        sorted_d2_tuples = sorted(d2.get_result_dict().items(), key=lambda d: d[1], reverse=True)
        d1_to_first = sorted_d1_tuples[0][1] - d1_party_result
        d1_to_second = sorted_d1_tuples[1][1] - d1_party_result
        d2_to_first = sorted_d2_tuples[0][1] - d2_party_result
        d2_to_second = sorted_d2_tuples[1][1] - d2_party_result

        if d1_to_first > d2_to_first:
            return 1
        elif d1_to_first < d2_to_first:
            return -1
        else:  # When the party we look at has the most votes
            # Look at the distance to the second place
            if d1_to_second > d2_to_second:
                return 1
            elif d1_to_second < d2_to_second:
                return -1
            else:  # If this should be miraculously the same check for the largest value
                if d1_party_result > d2_party_result:
                    return -1
                elif d1_party_result < d2_party_result:
                    return 1
                else:
                    return 0

    def add_district_to_bwk(target_district, target_bwk, district_diff=None):
        if not district_diff:
            district_diff = get_bwk_and_diff(target_district)[0]

        # Check if we got a diff already
        if district_diff:
            if target_bwk == target_district.bwk:
                diffs.remove(district_diff)
                db_session.delete(district_diff)
            else:
                district_diff.bwk = bwk

        # ... if not add one
        elif target_bwk != target_district.bwk:
            target_diff = Diff(target_district.identifier, target_bwk)
            db_session.add(target_diff)
            diffs.append(target_diff)

    # Returns the districts diff entry and current BWK
    def get_bwk_and_diff(district_to_check):
        loc_diff = next((x for x in diffs if x.identifier == district_to_check.identifier), None)

        if loc_diff:
            loc_bwk = loc_diff.bwk
        else:
            loc_bwk = district_to_check.bwk

        return loc_diff, loc_bwk

    # Sort by highest delta
    bwk_districts = sorted(bwk_districts, key=functools.cmp_to_key(district_comparator))
    county_result = {key: 0 for key in bwk_districts[0].get_result_dict().keys()}
    new_county_result = get_new_results(bwk_districts[0], county_result)
    new_county = []
    if check_winning_party(new_county_result, party):
        new_county.append(bwk_districts[0])
        bwk_districts = bwk_districts[1:]
        county_result = new_county_result

    # We try to expand our new county as far as possible...
    while len(new_county) > 0:
        new_new_county = []
        for district in new_county:
            if not district.neighbours:
                district.fill_neighbours()
            # ...by searching the neighbours of our glorious new county
            own_diff, own_bwk = get_bwk_and_diff(district)
            d_neighbours = get_neighbours(district, get_bwk_and_diff,
                                          lambda n_district, n_bwk:
                                          any(b_d.identifier == n_district.identifier for b_d in bwk_districts)
                                          or own_bwk != n_bwk)
            for neighbour, neighbour_diff, neighbour_bwk in d_neighbours:
                # Calculate the new result
                new_county_result = get_new_results(neighbour, county_result)
                new_neighbour_county_result = get_new_results(neighbour, results[neighbour_bwk], factor=-1)
                neighbour_county_winner = get_winning_party(results[neighbour_bwk])

                # Check if still win with this new district and that the old county's result is not changed

                if check_winning_party(new_county_result, party) and \
                        neighbour_bwk == bwk or \
                        check_winning_party(new_neighbour_county_result, neighbour_county_winner):

                    add_district_to_bwk(neighbour, bwk, neighbour_diff)
                    new_new_county.append(neighbour)
                    county_result = new_county_result
                    results[neighbour_bwk] = new_neighbour_county_result
                    if neighbour in bwk_districts:
                        bwk_districts.remove(neighbour)

        new_county = new_new_county

    # If we found a working solution
    if check_winning_party(county_result, party):

        forced = False

        # Check if we still have districts we have to move around
        while len(bwk_districts) > 0:
            changed = False
            for district in bwk_districts:

                if district.neighbours is None:
                    district.fill_neighbours()

                # Check if we got a diff for the current district to check our districts current BWK
                own_diff, own_bwk = get_bwk_and_diff(district)

                d_neighbours = get_neighbours(district, get_bwk_and_diff, lambda _, n_bwk: own_bwk != n_bwk)

                # Search for a neighbour who is in a different BWK
                for neighbour, neighbour_diff, neighbour_bwk in d_neighbours:
                    # Try to make sure that the result in the neighbours BWK is unchanged when we add this district
                    old_winner = sorted(results[neighbour_bwk], key=lambda x: x[1], reverse=True)[0][0]
                    n_results = neighbour.get_result_dict()
                    # Add the votes of this district to the total result of the bwk
                    for key in n_results.keys():
                        results[neighbour_bwk][key] += n_results[key]
                    # If the result in the BWK is unchanged
                    if forced or sorted(results[neighbour_bwk], key=lambda x: x[1], reverse=True)[0][0] == old_winner:
                        add_district_to_bwk(district, neighbour_bwk, own_diff)

                        bwk_districts.remove(district)
                        changed = True
                        forced = False

                        break
                    else:
                        for key in n_results.keys():
                            results[neighbour.bwk][key] -= n_results[key]
            # If we didn't find the perfect candidate just force the addition to the
            # first potential BWK and try again
            if not changed:
                forced = True

        db_session.commit()
    # If we found no working solution...
    else:
        pass
    # ...first check the original districts of the BWK...
    #    original_bwk_districts = MergedDistrict.query.filter(MergedDistrict.bwk == bwk)
    # ...sort again for the biggest delta...
    #    original_bwk_districts = sorted(bwk_districts, key=functools.cmp_to_key(district_comparator))
    # ...but this time only take the first entry and check if it makes our party win...
    #   if check_winning_party(original_bwk_districts[0].get_result_dict(), party):
    # ...add this district to our now county
    #       new_county = [original_bwk_districts[0]]
    # ...and remove it
    #       original_bwk_districts = original_bwk_districts[1:]
    # Also check if we got a diff for this district


def check_winning_party(voting_results, party):
    return get_winning_party(voting_results) == party


def get_winning_party(voting_results):
    return sorted(voting_results.items(), key=lambda x: x[1], reverse=True)[0][0]


def get_new_results(district, sums, factor=1):
    nc_results = district.get_result_dict()
    new_sums = sums.copy()
    for key in sums.keys():
        new_sums[key] += nc_results[key] * factor
    return new_sums


def get_neighbours(district, get_bwk, filter_function):
    # Get all neighbours that are not in the current districts BWK
    d_neighbours = []
    for n in district.neighbours:
        n_diff, n_bwk = get_bwk(n)
        if filter_function(district, n_bwk):
            d_neighbours.append((n, n_diff, n_bwk))
    return d_neighbours


if __name__ == '__main__':
    get_gerrymandering_steps('078', 'cdu')
