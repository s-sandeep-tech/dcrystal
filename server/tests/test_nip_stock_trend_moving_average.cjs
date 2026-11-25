const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/nip_stock_trend.js'), 'utf8');
const helper = source.slice(source.indexOf('    function selectedRangeMovingAverage('), source.indexOf('    function draw()'));
function average(dates, values) {
    const fn = vm.runInNewContext(helper + '\nselectedRangeMovingAverage;', { data: { balance_dates: dates } });
    return Array.from(fn(values));
}
const days = n => Array.from({ length: n }, (_, i) => new Date(Date.UTC(2026, 10, i + 1)).toISOString().slice(0, 10));

test('average uses all selected balances through the current date', () => {
    assert.deepEqual(average(days(8), [1,2,3,4,5,6,7,8]), [1,1.5,2,2.5,3,3.5,4,4.5]);
});

test('date gaps do not discard earlier selected balances', () => {
    assert.deepEqual(average(['2026-11-01','2026-11-02','2026-11-09'], [10,20,90]), [10,15,40]);
});

test('missing balances are excluded without filling the missing point', () => {
    assert.deepEqual(average(days(4), [10,null,30,20]), [10,null,20,20]);
});

test('zero balances count in the average', () => {
    assert.deepEqual(average(days(3), [0,10,20]), [0,5,10]);
});

test('each point uses only past and current balances', () => {
    const before = average(days(2), [10,20]);
    const after = average(days(3), [10,20,900]);
    assert.deepEqual(after.slice(0,2), before);
});

test('balances older than seven days still contribute within the selected range', () => {
    const result = average(days(14), [...Array(7).fill(100), ...Array(7).fill(10)]);
    assert.equal(result.at(-1), 55);
});

test('changing the selected date range resets the averaging window', () => {
    const dates = days(14), values = [...Array(7).fill(100), ...Array(7).fill(10)];
    assert.equal(average(dates, values).at(-1), 55);
    assert.deepEqual(average(dates.slice(7), values.slice(7)), Array(7).fill(10));
});

test('series stay independent and input balances are unchanged', () => {
    const values = Object.freeze([10,20,30]);
    assert.deepEqual(average(days(3), values), [10,15,20]);
    assert.deepEqual(average(days(3), [100,200,300]), [100,150,200]);
    assert.deepEqual(values, [10,20,30]);
});

test('empty and missing series do not generate artificial lines', () => {
    assert.deepEqual(average([], []), []);
    assert.deepEqual(average(days(2), [null,null]), [null,null]);
    assert.deepEqual(average(['invalid'], [10]), [null]);
});
