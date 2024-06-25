"""Reduce the result of a reduce regions FeatureCollection to a dictionary similar to the one returned by a reduceRegion"""

from functools import reduce
import ee

pathKey = "__path__"
parentPathKey = "__parentPath__"


def reduceFlattened(featureCollection, reducer, groupKeys):

    def flatten(feature):
        rootDict = feature.toDictionary()

        def f(groupDict, groupKey):

            groupDict = ee.Dictionary(groupDict)
            parentPath = ee.String(groupDict.get(parentPathKey, ""))
            group = groupDict.getNumber(groupKey).format("%d")
            path = parentPath.cat(group)
            nestedGroups = ee.List(groupDict.get("groups", [])).map(
                lambda nestedGroupDict: ee.Dictionary(nestedGroupDict).set(
                    parentPathKey, path.cat("_")
                )
            )

            return ee.Algorithms.If(
                nestedGroups.size(),
                nestedGroups,
                groupDict.set(pathKey, path).remove([parentPathKey, groupKey]),
            )

        flattened = ee.List(
            ee.List(groupKeys)
            .reverse()
            .iterate(
                lambda groupKey, groups: ee.List(groups)
                .map(lambda group: f(group, groupKey))
                .flatten(),
                rootDict.get("groups"),
            )
        )
        return ee.FeatureCollection(
            flattened.map(lambda dict_: ee.Feature(None, dict_))
        )

    merged = ee.FeatureCollection(
        featureCollection.iterate(
            lambda feature, acc: ee.FeatureCollection(acc).merge(flatten(feature)),
            ee.FeatureCollection([]),
        )
    )
    columns = merged.first().toDictionary().keys().remove(pathKey)

    return ee.List(
        merged.reduceColumns(
            reducer.group(0, pathKey), ee.List([pathKey]).cat(columns)
        ).get("groups")
    )


def reduceGroups(reducer, featureCollection, groupKeys):

    def accumulate(reducedDict, acc):

        reducedDict = ee.Dictionary(reducedDict)
        acc = ee.Dictionary(acc)
        path = reducedDict.getString(pathKey)
        groups = path.split("_").map(lambda group: ee.Number.parse(ee.String(group)))

        def create_level_structure(levels, groupKey):

            i = list(reversed(groupKeys)).index(groupKey)

            group = groups.get(i)
            prevLevel = levels[len(levels) - 1]
            defaultDict = ee.Dictionary({}).set(groupKey, group)
            groupDicts = ee.List(prevLevel.get("groups", []))
            groupDictMatches = ee.FeatureCollection(
                groupDicts.map(lambda dict_: ee.Feature(None, dict_))
            ).filter(ee.Filter.eq(groupKey, group))

            groupDict = ee.Dictionary(
                ee.Algorithms.If(
                    groupDictMatches.size(),
                    groupDictMatches.first().toDictionary(),  ## Group aready exists, use old
                    defaultDict,
                )
            )

            updatedPrevLevelGroupDicts = ee.List(
                ee.Algorithms.If(
                    groupDictMatches.size(),
                    groupDicts,  ## Group aready exists, return old
                    groupDicts.add(defaultDict),  ## Add new group
                )
            )
            updatedPrevLevel = prevLevel.set("groups", updatedPrevLevelGroupDicts)

            return levels[:-1] + [updatedPrevLevel, groupDict]

        levels = reduce(create_level_structure, reversed(groupKeys[:]), [acc])

        def update_levels(acc, i_and_level):

            i, level = i_and_level

            level = ee.Dictionary(level)
            acc = ee.Dictionary(acc)

            groupKey = groupKeys[i]
            group = groups.reverse().get(i)  ## We're iterating levels in reverse order
            groupDicts = ee.List(level.get("groups", []))
            groupDictMatches = ee.FeatureCollection(
                groupDicts.map(lambda group: ee.Feature(None, group))
            ).filter(ee.Filter.eq(groupKey, group))
            updatedGroups = ee.Algorithms.If(
                groupDictMatches.size(),
                groupDicts.replace(groupDictMatches.first().toDictionary(), acc),
                groupDicts.add(acc),
            )
            updatedLevel = level.set("groups", updatedGroups)
            return updatedLevel

        leaf = levels[len(levels) - 1].combine(reducedDict.remove([pathKey]))

        # // TODO: We're missing previous values
        # Use slicing ([:]) to copy the list, reverse it, and then reduce it
        return ee.Dictionary(reduce(update_levels, enumerate(levels[:-1][::-1]), leaf))

    reduced = reduceFlattened(featureCollection, reducer, groupKeys)

    # Iterate an algorithm over a list. The algorithm is expected to take two objects,
    # the current list item, and the result from the previous iteration or the value of
    # first for the first iteration.
    return ee.Dictionary(
        reduced.iterate(function=accumulate, first=ee.Dictionary())
    ).get("groups")
